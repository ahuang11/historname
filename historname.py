import glob
import gc
import param
import sqlite3
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
# (df['newborns'].reset_index('name').drop('name', axis=1)
#     .drop_duplicates('newborns').to_pickle('newborns.1880.2017.pkl'))
# df = df.drop(['F', 'M', 'newborns'], axis=1)
# df.drop('pct_male', axis=1)
# df.to_pickle('processed.yob.1880.2017.pkl')
# df = pd.read_pickle('processed.yob.1880.2017.pkl')

# DB_NAME = 'newborns.db'
# conn = sqlite3.connect(DB_NAME)
# df.to_sql('newborn_names', conn, if_exists='append')
# newborns.to_sql('newborns', conn, if_exists='append')
# conn.commit()
# conn.close()

NAME = 'Name'
ANDSTAR = 'And*'
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
    Wildcard (*) is supported; will return the top 5 names.<br>
    <br>
"""
DB_NAME = 'newborns.db'

SQL_QUERY_FMT = """
    SELECT year, name, count, pct_female, pct_newborns
    FROM newborn_names
    WHERE name in
        (SELECT name
         FROM newborn_names
         WHERE name
         LIKE ?
         GROUP BY name
         ORDER BY sum(count)
         DESC LIMIT 5
         )
"""
TITLE_FMT = 'Percent of US Newborns Named {0} Each Year'
SUMMARY_FMT = ("Most popular year was in {0} where\n"
               "{1:,.0f} newborns were named {2}.\n"
               "That's {4:.2f}% of {3:,.0f} newborns.")

HOVER = HoverTool(
    tooltips=[
        ('Name', '@name'),
        ('Year', '@year{int}'),
        ('Count', '@count{int}'),
        ('% of Newborns', '@pct_newborns{0.00f}%'),
        ('% Female', '@pct_female{0.00f}%')
    ],
)


def _query_name(name):
    name = name.title().strip(' ').replace('*', '%')
    df = pd.read_sql_query(SQL_QUERY_FMT, conn, params=(name,))
    return df


def _decide_year(top_name, name_tot):
    name_tot_sub = (name_tot.query('name == "{0}"'.format(top_name)
                                   ))
    if name_tot_sub.index[0] >= 1905:
        min_year = 1882
    else:
        min_year = (name_tot_sub
                    .loc[name_tot_sub['pct_newborns'].idxmin()])
    return min_year['year']


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


def _finalize_obj(hv_obj, points=False):
    hv_obj = (hv_obj
        .redim.range(year=(1865, 2035))
        .redim.label(pct_newborns='Percent [%]')
        .redim.label(year='Year')
        .options(show_grid=True,
                 width=1050,
                 height=600,
                 toolbar='above'))
    if not points:
        hv_obj = hv_obj.options(tools=[HOVER])

    return hv_obj


def plot_pct_of_newborns(name):
    name_tot = _query_name(name)
    name_tseries = _finalize_obj(
        name_tot.hvplot('year', 'pct_newborns',
                        groupby=['name'],
                        hover_cols=['count', 'pct_female'],
                        ).overlay('name')
    )

    name_points = _finalize_obj(
        name_tot.hvplot.points('year', 'pct_newborns',
                               hover=False,
                               hover_cols=['name', 'count', 'pct_female'],
                               cmap='RdYlBu_r'
                               )
        .options(color_index='pct_female', colorbar=True, marker='s',
                 colorbar_opts={'title': '%F'}, size=10,
                 alpha=0.25, line_color='lightgray', line_alpha=0.35)
        .redim.range(pct_female=(0, 100), points=True)
    )

    top_name = name_tot.groupby('name').sum().sort_values(
        'count', ascending=False).index[0]
    min_year = _decide_year(top_name, name_tot)
    text_align, text_offset = _smart_align(min_year)

    name_max = name_tot.loc[name_tot['pct_newborns'].idxmax()]
    name_max_year = name_max.year
    summary_kwds = [name_max_year, name_max['count'], top_name,
                    newborns.loc[name_max_year].values[0],
                    name_max['pct_newborns']]
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

    enter_first_name_below = param.String(default=ANDSTAR)

    output = parambokeh.view.Plot()

    def view(self, *args, **kwargs):
        return plot_pct_of_newborns(self.enter_first_name_below)

    def event(self, **kwargs):
        gc.collect()
        # clear canvas and replace
        if not self.output:
            self.output = hv.DynamicMap(self.view, streams=[self])
        else: # update canvas with new name
            super(Historname, self).event(**kwargs)


# initialize newborns count
newborns = pd.read_pickle('newborns.1880.2017.pkl')
# initialize connection to database
conn = sqlite3.connect(DB_NAME)

selector = Historname(name='Historname')
parambokeh.Widgets(selector,
                   width=450,
                   on_init=True,
                   mode='server',
                   view_position='right',
                   callback=selector.event)
