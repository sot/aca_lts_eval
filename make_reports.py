import os
import re
import shutil
import numpy as np
import jinja2
import matplotlib
if __name__ == '__main__':
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from Ska.Matplotlib import plot_cxctime
from astropy.table import Table
from Chandra.Time import DateTime

import warnings
# Ignore known numexpr.necompiler and table.conditions warning
warnings.filterwarnings(
    'ignore',
    message="using `oa_ndim == 0` when `op_axes` is NULL is deprecated.*",
    category=DeprecationWarning)


import aca_required_temp

targets = Table.read('aca_target_data_venus.txt', format='ascii.basic', data_start=2)
LABEL = 'Venus'
OUTDIR = 'venus'

PLANNING_LIMIT = -14

start = DateTime('2015:298')
stop = DateTime('2015:301')

report = []

for t in targets[:2]:
    obsdir = os.path.join(OUTDIR, 'obs{:05d}'.format(t['ObsID']))
    if not os.path.exists(obsdir):
        os.makedirs(obsdir)
    print('Processing obsid {}'.format(t['ObsID']))

    t_ccd_table = aca_required_temp.make_target_report(t['RA'], t['Dec'],
                                                       t['Yoff'], t['Zoff'],
                                                       start=start,
                                                       stop=stop,
                                                       obsdir=obsdir,
                                                       obsid=t['ObsID'],
                                                       debug=False,
                                                       redo=True)

    report.append({'obsid': t['ObsID'],
                   'obsdir': obsdir,
                   'ra': t['RA'],
                   'dec': t['Dec'],
                   'max_nom_t_ccd': np.nanmax(t_ccd_table['nom_t_ccd']),
                   'min_nom_t_ccd': np.nanmin(t_ccd_table['nom_t_ccd']),
                   'max_best_t_ccd': np.nanmax(t_ccd_table['best_t_ccd']),
                   'min_best_t_ccd': np.nanmin(t_ccd_table['best_t_ccd']),
                   })

report = Table(report)['obsid', 'obsdir', 'ra', 'dec',
                       'max_nom_t_ccd', 'min_nom_t_ccd',
                       'max_best_t_ccd', 'min_best_t_ccd']
report.sort('min_nom_t_ccd')
formats = {
    'obsid': '%i',
    'obsdir': '%s',
    'ra': '%6.3f',
    'dec': '%6.3f',
    'max_nom_t_ccd': '%5.2f',
    'min_nom_t_ccd': '%5.2f',
    'max_best_t_ccd': '%5.2f',
    'min_best_t_ccd': '%5.2f'}


#html_table = report.pformat(html=True, max_width=-1, max_lines=-1)
# customize table for sorttable
#new_table = ['<table class="sortable" border cellpadding=5>']
#new_table.append(html_table[1])
#new_table.append(re.sub('<th>obsid</th>',
#                        '<th>obsid<span id="sorttable_sortfwdind">&nbsp;&#9662;</span></th>',
#                        html_table[1]))
# just an idea for marking up obsids that are likely to hit the planning
# limit in red
#for row in html_table[2:]:
#    new_row = re.sub('<td>True</td>',
#                     '<td><font color="red">True</font></td>',
#                     row)
#    obs_match = re.search("<tr><td>(\d{1,5})</td>", new_row)
#    if obs_match:
#        new_row = re.sub("<tr><td>\d{1,5}</td>",
#                         "<tr><td><a href='obs{}/index.html'>{}</a></td>".format(
#                obs_match.group(1), obs_match.group(1)),
#                         new_row)
#    new_table.append(new_row)

report.write(os.path.join(OUTDIR, "target_table.dat"),
             format="ascii.fixed_width_two_line")

shutil.copy('sorttable.js', OUTDIR)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))
jinja_env.line_comment_prefix = '##'
jinja_env.line_statement_prefix = '#'
template = jinja_env.get_template('toptable.html')
page = template.render(table=report,
                       formats=formats,
                       planning_limit=PLANNING_LIMIT,
                       start=start.fits,
                       stop=stop.fits,
                       label='ACA Evaluation of Targets')
f = open(os.path.join(OUTDIR, 'index.html'), 'w')
f.write(page)
f.close()



