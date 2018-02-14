import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import matplotlib.gridspec as gridspec
from datetime import timedelta, datetime, date

from gmailaccount import GmailAccount

#This has been based on the blog post http://beneathdata.com/how-to/email-behavior-analysis/. Unless indicated all comments in this code come from the original blog post

gmail = GmailAccount(username='email', password='password')
gmail.login()

daysback = 2500 # ~7yrs
notsince = 0 # since now.
since = (date.today() - timedelta(daysback)).strftime("%d-%b-%Y")
before = (date.today() - timedelta(notsince)).strftime("%d-%b-%Y")

SEARCH = '(SENTSINCE {si} SENTBEFORE {bf})'.format(si=since, bf=before)
ALL_HEADERS = '(BODY.PEEK[HEADER.FIELDS (DATE TO CC FROM SUBJECT)])'

# Search and fetch emails!
received = gmail.load_parse_query(search_query=SEARCH, fetch_query=ALL_HEADERS, folder='"[Gmail]/Sent Mail"')

def scrub_email(headers):   
     #IMAP sometimes returns fields with varying capitalization. Lowercase each header name.
    return dict([(title.lower(), value) for title, value in headers]) 

df = pd.DataFrame([scrub_email(email._headers) for email in received])
def try_parse_date(d):
    try:
        ts = pd.Timestamp(d)
        # IMAP is very much not perfect...some of my emails have no timezone
        # in their date string.
        if ts.tz is None: 
            ts = ts.tz_localize('UTC')
        # I moved from Great Britain to Copenhagen in August 2015, so automatically assume UTC/CET
        # before/after that date (chris).
        if ts < pd.Timestamp('2015-09-15', tz='CET'):
            ts = ts.tz_convert('GMT')
        else:
            ts = ts.tz_convert('CET')
        # Here's the magic to use timezone-naive timestamps
        return pd.Timestamp(ts.to_datetime().replace(tzinfo=None))

    except:
        # If we fail, return NaN so pandas can remove this email later.
        return np.nan

df['timestamp'] = df.date.map(try_parse_date)
# Remove any emails that Timestamp was unable to parse
df = df.dropna(subset=['timestamp'])

df['hour'] = df.timestamp.map(lambda x: x.hour)

freq = 'M' # could also be 'W' (week) or 'D' (day), but month looks nice.
df = df.set_index('timestamp', drop=False)
df.index = df.index.to_period(freq)

mindate = df.timestamp.min()
maxdate = df.timestamp.max()
pr = pd.period_range(mindate, maxdate, freq=freq)
# Initialize a new HeatMap dataframe where the indicies are actually Periods of time
# Size the frame anticipating the correct number of rows (periods) and columns (hours in a day)
hm = pd.DataFrame(np.zeros([len(pr), 24]) , index=pr)

for period in pr:
    # HERE'S where the magic happens...with pandas, when you structure your data correctly,
    # it can be so terse that you almost aren't sure the program does what it says it does...
    # For this period (month), find relevant emails and count how many emails were received in
    # each hour of the day. Takes more words to explain than to code.
    if period in df.index:
        hm.ix[period] = df.ix[[period]].hour.value_counts()

# If for some weird reason there was ever an hour period where you had no email,
# fill those NaNs with zeros.
hm.fillna(0, inplace=True)

fig = plt.figure(figsize=(12,8))
# This will be useful later
gs = gridspec.GridSpec(2, 2, height_ratios=[4,1], width_ratios=[20,1],)
gs.update(wspace=0.05)

### Plot our heatmap
ax = plt.subplot(gs[0])
x = dates.date2num([p.start_time for p in pr])
t = [datetime(2011, 1, 4, h, 0, 0) for h in range(24)]
t.append(datetime(2011, 1, 5, 0, 0, 0)) # add last fencepost
y = dates.date2num(t)
cm = plt.get_cmap('Oranges')
plt.pcolor(x, y, hm.transpose().as_matrix(), cmap=cm)

### Now format our axes to be human-readable
ax.xaxis.set_major_formatter(dates.DateFormatter('%b %Y'))
ax.yaxis.set_major_formatter(dates.DateFormatter('%H:%M'))
ax.set_yticks(t[::2])
ax.set_xticks(x[::12])
ax.set_xlim([x[0], x[-1]])
ax.set_ylim([t[0], t[-1]])
ax.tick_params(axis='x', pad=14, length=10, direction='inout')

### pcolor makes it sooo easy to add a color bar!
plt.colorbar(cax=plt.subplot(gs[1]))

ax2 = plt.subplot(gs[2])
total_email = df.groupby(level=0).hour.count()
#In the original post I could not get plot_date to work when x is an index of a Dataframe. Fortunately x is converted into the correct format (chris).
plt.plot_date(x,total_email, '-', linewidth=1.5, color=cm(0.999))
ax2.fill_between(x, 0, total_email, color=cm(0.5))
ax2.set_xlim([x[0], x[-1]])

ax2.xaxis.tick_top()
out = ax2.set_xticks(x[::12])
out = ax2.xaxis.set_ticklabels([])
ax2.tick_params(axis='x', pad=14, length=10, direction='inout')
plt.savefig('visualising_received_email_data.png')
plt.show()
