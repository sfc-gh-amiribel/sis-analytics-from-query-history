# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(layout="centered", page_title="SiS Analytics")


@st.cache_data
def get_query_history() -> pd.DataFrame:
    data = pd.read_csv("query_history.csv")
    data["start_date"] = pd.to_datetime(data.start_time).dt.date
    return data


SAMPLE_SQL_QUERY = """
select
    start_time as start_time,
    user_name as viewer_name,
    try_parse_json(query_tag)['team_name']::string as team_name,
    try_parse_json(query_tag)['app_name']::string as app_name,
    try_parse_json(query_tag)['page_name']::string as page_name,
    database_name,
    schema_name,
    query_text as query_text,
    query_type,
    query_id,
    (total_elapsed_time / 1000)::float as query_time_sec
from snowflake.account_usage.query_history
where
    try_parse_json(query_tag)['project_name']::string = 'sis_analytics_with_query_tags'
"""

st.title("Streamlit in Snowflake Analytics")

blog_post_url = "https://medium.com/snowflake/streamlit-in-snowflake-analytics-made-easy-using-query-tags-bcf728c86802"

f""" This is a sample app to illustrate what insights you could get after
 setting up query tags in your Streamlit in Snowflake apps. Read more in the
 [Medium blog post]({blog_post_url}) 🪼"""

data = get_query_history()

with st.expander("Dataset", expanded=False):
    """We use a dummy query history dataset that is a plausible
    result of the following query, as explained in the blog post:"""
    st.caption("Input SQL:")
    st.code(SAMPLE_SQL_QUERY, language="sql")
    st.caption("Dummy output:")
    st.dataframe(data, use_container_width=True)

""" ## Summary """


@st.cache_data
def summary(data: pd.DataFrame) -> None:
    left, middle, right = st.columns(3)
    left.metric("Total num. of teams", data.team_name.dropna().nunique())
    middle.metric(
        "Total num. of apps",
        len(data[["team_name", "app_name"]].dropna().drop_duplicates()),
    )
    right.metric(
        "Total num. of pages",
        len(data[["team_name", "app_name", "page_name"]].dropna().drop_duplicates()),
    )


summary(data)

""" ## Explore """

start_date, end_date = st.date_input(
    "Date range",
    (data.start_date.min(), data.start_date.max()),
    data.start_date.min(),
    data.start_date.max(),
)

data = data[data.start_date.between(left=start_date, right=end_date)]

team = st.selectbox(
    "Team", ["All"] + data.team_name.dropna().unique().tolist(), index=1
)

if team != "All":
    data = data[data.team_name == team]

left, right = st.columns(2)
app_options = ["All"] + data.app_name.dropna().unique().tolist()
app = left.selectbox("App", app_options, disabled=team == "All", index=2)

if app != "All":
    data = data[data.app_name == app]

page_options = ["All"] + data.page_name.dropna().unique().tolist()
page = right.selectbox("Page", page_options, disabled=app == "All")

if page != "All":
    data = data[data.page_name == page]

st.divider()

if data.empty:
    st.warning("No data to display")
    st.stop()

""" ## Viewers """
""" Selected app(s) """

viewers_data = (
    data.groupby("start_date")
    .viewer_name.apply(set)
    .to_frame("Viewers")
    .sort_values(by="start_date", ascending=False)
)
viewers_data["Unique viewers"] = viewers_data.Viewers.apply(len)
st.dataframe(viewers_data, use_container_width=True)


""" Selected page(s) """
viewers_data = (
    data.groupby(["start_date", "app_name", "page_name"])
    .viewer_name.apply(set)
    .to_frame("Viewers")
    .sort_values(by="start_date", ascending=False)
)
viewers_data["Unique viewers"] = viewers_data.Viewers.apply(len)
st.dataframe(viewers_data, use_container_width=True)


def percentile(n):
    def percentile_(x):
        return x.quantile(n)

    percentile_.__name__ = "percentile_{:02.0f}".format(n * 100)
    return percentile_


""" ## Performance """
""" Daily quantiles """

# Compute the quartiles and other statistics
quartiles = (
    data.groupby("start_date")["query_time_sec"]
    .quantile([0, 0.25, 0.5, 0.9, 0.95, 1])
    .unstack()
)
column_names = ["min", "p25", "median", "p90", "p95", "max"]
quartiles.columns = column_names
quartiles.reset_index(inplace=True)

# Create a new DataFrame for plotting
plot_data = pd.melt(quartiles, id_vars="start_date", value_vars=column_names)

# Create the boxplot in Altair
chart = (
    alt.Chart(
        plot_data,
        height=400,
    )
    .mark_line()
    .encode(
        x=alt.X("yearmonthdate(start_date):T", title="Date"),
        y=alt.Y(
            "value:Q",
            scale=alt.Scale(zero=False, type="log"),
            title="Query duration (sec)",
        ),
        color=alt.Color("variable:N", sort=column_names[::-1]),
    )
)

st.altair_chart(chart, use_container_width=True)

""" 100 Longest queries """

st.dataframe(
    data.sort_values(by="query_time_sec", ascending=False)
    .head(100)[
        [
            "start_date",
            "team_name",
            "app_name",
            "page_name",
            "query_text",
            "query_time_sec",
        ]
    ]
    .reset_index(drop=True),
    use_container_width=True,
)
