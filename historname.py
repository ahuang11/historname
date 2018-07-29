import glob
import param
import parambokeh
import pandas as pd
import hvplot.pandas
import holoviews as hv

from holoviews.streams import Stream
from bokeh.models import Axis, HoverTool

# https://github.com/bokeh/bokeh/pull/8062
from bokeh.themes import built_in_themes
hv.renderer('bokeh').theme = built_in_themes['light_minimal']
hv.extension('bokeh')

# already processed
# df = pd.read_csv('yob.1880.2017.txt')
# gender_df = df.groupby(['gender', 'year', 'name'],
#                        as_index=False).sum().pivot_table(
#     index=['year', 'name'], columns=['gender'], values='count').fillna(0)
# gender_df['pct_female'] = gender_df['F'] / gender_df.sum(axis=1) * 100
# gender_df['pct_male'] = 100. - gender_df['pct_female']
# df = pd.read_csv('yob.1880.2017.txt')
# df = df.groupby(['year', 'name']).sum()
# df = (df.join(df.groupby(level='year').sum()
#               .rename(columns={'count': 'newborns'})
#               ).join(gender_df)
#      )
# df['pct_newborns'] = df['count'] / df['newborns'] * 100

df = pd.read_pickle('processed.yob.1880.2017.pkl')

NAME = 'Name'
ANDREW = 'Andrew'
NOTES = """
    <br>
    <br>
    For any given year:<br>
    <br>
    Redder indicates higher % of females.<br>
    <br>
    Bluer indicates higher % of males.<br>
    <br>
    Whiter indicates similar % of both.<br>
    <br>
    Data does not include names of immigrants.<br>
    <br>
    Different spellings of a name are not aggregated.<br>
    <br>
    Names with fewer than 5 occurrences are not shown.<br>
    <br>
    For more information see: ssa.gov/oact/babynames/background.html<br>
    <br>
"""


QUERY_FMT = 'name == "{0}"'
TITLE_FMT = 'Percent of US Newborns Named {0} Each Year'
SUMMARY_FMT = ("Most popular year was in {0} where\n"
               "{1:,.0f} newborns were named {2}.\n"
               "That's {4:.2f}% of {3:,.0f} newborns.")

HOVER = HoverTool(
    mode='vline',
    tooltips=[
        ('Year', '@year{int}'),
        ('Count', '@count{int}'),
        ('% of Pop.', '@pct_newborns{0.00f}%'),
        ('% Female', '@pct_female{0.00f}%'),
        ('% Male', '@pct_male{0.00f}%')
    ],
)


def _query_name(df, name):
    return df.query(QUERY_FMT.format(name))


def _force_float(plot, element):
    p = plot.state
    yaxis = p.select(dict(type=Axis, layout="left"))[0]
    yaxis.formatter.use_scientific = False
    return p

def _decide_year(name_tot):
    if name_tot.index[0] >= 1905:
        min_year = 1882
    else:
        min_year = (name_tot
                    .loc[name_tot['pct_newborns'].idxmin()]
                    .name)
    return min_year

def _smart_align(year):
    if year <= 1935:
        text_align = 'left'
        text_offset = -13
    elif year >= 1965:
        text_align = 'right'
        text_offset = 13
    else:
        text_align = 'center'
        text_offset = 0
    return text_align, text_offset

def _finalize_obj(hv_obj, name, points=False):
    hv_obj = (hv_obj
        .redim.range(year=(1865, 2035))
        .redim.label(pct_newborns='Percent [%]')
        .redim.label(year='Year')
        .relabel(TITLE_FMT.format(name))
        .options(show_grid=True, color='black',
                 finalize_hooks=[_force_float],
                 show_legend=False,
                 alpha=0.45,
                 width=1000,
                 height=600))
    if points:
        hv_obj = (hv_obj
                  .options(color_index='pct_female',
                           colorbar_opts={'title': '%F'},
                           colorbar=True,
                           cmap='RdBu_r',
                           size=10)
                  .redim.range(pct_female=(0, 100))
                  )
    else:
        hv_obj = hv_obj.options(tools=[HOVER])
    return hv_obj

def plot_pct_of_newborns(df, name):
    name = name.title().strip(' ')
    name_tot = _query_name(df, name).groupby('year').sum()
    name_tseries = _finalize_obj(
        name_tot.hvplot('year', 'pct_newborns',
                        hover_cols=['count', 'pct_female', 'pct_male']),
        name)
    name_points = _finalize_obj(
        name_tot.hvplot.points('year', 'pct_newborns', hover=False,
                               hover_cols=['count', 'pct_female']),
        name, points=True)
    min_year = _decide_year(name_tot)
    text_align, text_offset = _smart_align(min_year)

    name_max = name_tot.loc[name_tot['pct_newborns'].idxmax()]
    summary_kwds = [name_max.name, name_max['count'], name,
                    name_max['newborns'], name_max['pct_newborns']]
    name_summary = (hv.Text(min_year + text_offset,
                            name_tot['pct_newborns'].quantile(0.985),
                            SUMMARY_FMT.format(*summary_kwds))
                    .options(color='#5B5B5B', text_align=text_align,
                             text_baseline='top', text_font_size='1.05em',
                             text_font='Helvetica', text_alpha=0.65)
                    )
    return name_tseries * name_points * name_summary


class Historname(Stream):
    """Highest level function to run the interactivity
    """

    notes = param.Parameter(default=NOTES,
                            constant=True,
                            precedence=0)

    enter_first_name_below = param.String(default=ANDREW)

    output = parambokeh.view.Plot()

    def view(self, *args, **kwargs):
        return plot_pct_of_newborns(df, self.enter_first_name_below)

    def event(self, **kwargs):
        # clear canvas and replace
        if not self.output:
            self.output = hv.DynamicMap(self.view, streams=[self])
        else: # update canvas with new name
            super(Historname, self).event(**kwargs)

selector = Historname(name='Historname')
parambokeh.Widgets(selector,
                   width=450,
                   on_init=True,
                   mode='server',
                   view_position='right',
                   callback=selector.event)
