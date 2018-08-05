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
# from bokeh.themes import built_in_themes
# hv.renderer('bokeh').theme = built_in_themes['light_minimal']
# hv.extension('bokeh')

NAME = 'name'
YEAR = 'year'
COUNT = 'count'
PCT_FM = 'pct_female'
PCT_NB = 'pct_newborns'
NEWBORNS = 'newborns'

WIDTH = 1050
HEIGHT = 600
WIDGET_WIDTH = 400
YEARS = (1880, 2017)

DEFAULT_COLORS = ['red', 'blue', 'orange', 'green', 'purple']

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
    Yellower indicates similar % of both.<br>
    <br>
    Data does not include names of immigrants.<br>
    <br>
    Different spellings of a name are not aggregated.<br>
    <br>
    Names with fewer than 5 occurrences are not shown.<br>
    <br>
    For more information see:<br>
    ssa.gov/oact/babynames/background.html<br>
    github.com/ahuang11/historname
    <br>
    Wildcard (*) is supported; will return the top 5 names.<br>
    <br>
"""

DB_NAME = '{0}.db'.format(NEWBORNS)

SQL_QUERY_FMT = """
    SELECT {year}, {name}, {count}, {pct_fm}, {pct_nb}
    FROM newborn_names
    WHERE {name} in
        (SELECT {name}
         FROM newborn_names
         WHERE {name}
         LIKE ?
         GROUP BY {name}
         ORDER BY sum({count})
         DESC LIMIT 5
         )
    AND {year} >= ? AND {year} <= ?;
""".format(name=NAME, year=YEAR, count=COUNT,
           pct_fm=PCT_FM, pct_nb=PCT_NB)

TITLE_FMT = 'Percent of US Newborns Named {0} Each Year'
SUMMARY_FMT = ("{0} had the most newborns named\n"
               "{2}: {1:,.0f} out of {3:,.0f}\n"
               "newborns, or {4:.2f}% of all newborns.")

HOVER = HoverTool(
    tooltips=[
        ('Name', '@name'),
        ('Year', '@year{int}'),
        ('Count', '@count{int}'),
        ('% of Newborns', '@pct_newborns{0.00f}%'),
        ('% Female', '@pct_female{0.00f}%')
    ],
)


def _query_name(name, years):
    name = name.title().strip(' ').replace('*', '%')
    df = pd.read_sql_query(SQL_QUERY_FMT, conn, params=(
        name, years[0], years[1]))
    return df


def _decide_year(top_name, name_tot):
    name_tot_sub = (name_tot.query(
        '{0} == "{1}"'.format(NAME, top_name)))

    if name_tot_sub.index[0] >= 1905:
        min_year = name_tot_sub.index[0] - 20
    else:
        min_year = (name_tot_sub
                    .loc[name_tot_sub[PCT_NB].idxmin()])

    return min_year[YEAR]


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


def _finalize_obj(hv_obj, years, hover=True):
    # subtract/add 25 to pad the text
    hv_obj = (hv_obj
        .redim.range(year=(years[0] - 20, years[1] + 20))
        .redim.label(pct_newborns='Percent [%]')
        .redim.label(year=YEAR.title())
        .options(show_grid=True,
                 width=WIDTH,
                 height=HEIGHT,
                 toolbar='above'))

    if hover:
        hv_obj = hv_obj.options(tools=[HOVER])

    return hv_obj


def plot_pct_of_newborns(name, years):
    name_tot = _query_name(name, years)
    name_tseries = _finalize_obj(
        name_tot.hvplot(YEAR, PCT_NB,
                        hover=False,
                        groupby=[NAME],
                        color=DEFAULT_COLORS,
                        hover_cols=[COUNT, PCT_FM],
                        ).overlay(NAME), years, hover=False
    )

    name_points = _finalize_obj(
        name_tot.hvplot.points(YEAR, PCT_NB,
                               hover=False,
                               hover_cols=[NAME, COUNT, PCT_FM],
                               cmap='RdYlBu_r'
                               )
        .options(color_index=PCT_FM, colorbar=True, marker='o',
                 colorbar_opts={'title': '%F'}, size=15,
                 alpha=0.15, line_color='lightgray', line_alpha=0.35)
        .redim.range(pct_female=(0, 100)), years
    )

    top_year, top_name, top_count, top_pct_female, top_pct_newborns = (
        name_tot.loc[name_tot[COUNT] ==
                     name_tot[COUNT].max()].values[0])
    min_year = _decide_year(top_name, name_tot)
    text_align, text_offset = _smart_align(min_year)
    summary_kwds = [top_year, top_count, top_name,
                    newborns.loc[top_year][0],
                    top_pct_newborns]

    name_summary = (hv.Text(min_year + text_offset,
                            name_tot[PCT_NB].quantile(0.985),
                            SUMMARY_FMT.format(*summary_kwds))
                    .options(color='#5B5B5B', text_align=text_align,
                             text_baseline='top', text_font_size='1.05em',
                             text_font='Helvetica', text_alpha=0.65)
                    )

    return (name_tseries * name_points * name_summary)


class Historname(Stream):
    """Highest level function to run the interactivity
    """
    notes = param.Parameter(default=NOTES,
                            constant=True,
                            precedence=0)

    select_years = param.Range(YEARS, bounds=YEARS)

    enter_first_name_below = param.String(default=ANDSTAR)

    output = parambokeh.view.Plot()

    def view(self, *args, **kwargs):
        return plot_pct_of_newborns(
            self.enter_first_name_below, self.select_years)

    def event(self, **kwargs):
        gc.collect()
        # clear canvas and replace
        if not self.output:
            self.output = hv.DynamicMap(self.view, streams=[self])
        else: # update canvas with new name
            super(Historname, self).event(**kwargs)


# initialize newborns count
newborns = pd.read_pickle('{0}.{1}.{2}.pkl'.format(NEWBORNS, *YEARS))
# initialize connection to database
conn = sqlite3.connect(DB_NAME)

selector = Historname(name='Historname')
parambokeh.Widgets(selector,
                   on_init=True,
                   mode='server',
                   width=WIDGET_WIDTH,
                   view_position='right',
                   callback=selector.event)
