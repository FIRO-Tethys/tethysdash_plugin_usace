from intake.source import base
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import re
import plotly.graph_objects as go


class TimeSeries(base.DataSource):
    container = 'python'
    version = '0.0.1'
    partition_access = True
    name = 'usace_time_series'
    _user_parameters = []

    def __init__(self, location, year, github_kwargs={}, metadata=None):
        # store important kwargs
        self.location = location
        self.year = year if year else get_water_year(datetime.now())
        self.data_groups = {}
        self.ymarkers = {}
        self.title = ""
        self.time_series_data = None
        self.plot_series = None
        super(TimeSeries, self).__init__(metadata=metadata)

    def read(self):
        """Return a version of the xarray with all the data in memory"""
        self._load_metadata()
        return go.Figure(data=self.plot_series, layout=self.layout)

    def _get_schema(self):
        plot_metadata = self.get_usace_metadata()
        self.data_groups = plot_metadata['data_groups']
        self.ymarkers = plot_metadata["ymarkers"]
        self.title = plot_metadata["title"]

        self.time_series_data = self.get_usace_data()
        self.get_plot_layout()
        self.get_plot_series()
        
        return base.Schema(
            datashape=None,
            dtype=None,
            shape=None,
            npartitions=1,  # This data is not partitioned, so there is only one partition
            extra_metadata={}
        )

    def _close(self):
        pass

    @staticmethod
    def parse_usace_data(data):
        print("Parsing CWMS Data")
        data = [data_point.split(",") for data_point in data.text.split("\n")]
        columns = [data_point.replace('"', "") for data_point in data[0]]
        df = pd.DataFrame(data[1:-1], columns=columns)
        drop_columns = [column for column in columns if "notes" in column]
        drop_columns.append("ISO 8601 Date Time")
        dates = df["ISO 8601 Date Time"].tolist()
        # fix issue where hour 24 is used instead of hour 0
        dates = [
            (
                pd.to_datetime(date.replace("T24", "T00")).tz_convert("UTC")
                + timedelta(days=1)
                if re.findall(".*-(.*)T24", date)
                else pd.to_datetime(date).tz_convert("UTC")
            )
            for date in dates
        ]
        df["Datetime"] = dates
        df = df.drop(columns=drop_columns)
        df = df[~(df["Datetime"] >= pd.to_datetime(datetime.now(timezone.utc), utc=True))]
        df = df.replace("-", np.nan)
    
        return df
    
    @staticmethod
    def merge_dataframe(df, new_df):
        df = df.set_index("Datetime")
        new_df = new_df.set_index("Datetime")
        df.update(new_df, overwrite=False)
    
        return df.reset_index()

    @staticmethod
    def get_water_year(date):
        if date.month >= 10:
            return date.year + 1
        return date.year

    def get_usace_data(self):
        """API controller for the plot page."""
        print("Getting CWMS Data")
        hourly_data = self.get_usace_plot_data(time_period="h")
        hourly_data = self.parse_usace_data(hourly_data)
        # For some reason, some hourly files are missing flows, so pull in daily averages where needed  # noqa: E501
        daily_data = self.get_usace_plot_data(time_period="d")
        daily_data = self.parse_usace_data(daily_data)
    
        df = self.merge_dataframe(hourly_data, daily_data)
        return df

    def get_usace_metadata(self):
        """API controller for the plot page."""
        return_obj = {}
        metadata = self.get_usace_plot_data(metadata=True)
        if not metadata:
            metadata = self.get_usace_plot_data(metadata=True, time_period="d")

        metadata = metadata.json()
        data_groups = {
            "storage": metadata["groups"]["storage"],
            "elevation": metadata["groups"]["elev"],
            "flow": [],
        }
        if metadata["groups"].get("topcon"):
            data_groups["storage"] += metadata["groups"]["topcon"]
    
        if metadata["groups"].get("inflow"):
            data_groups["flow"] += metadata["groups"]["inflow"]
    
        if metadata["groups"].get("outflow"):
            data_groups["flow"] += metadata["groups"]["outflow"]
    
        if metadata["groups"].get("flow"):
            data_groups["flow"] += metadata["groups"]["flow"]
    
        if metadata["groups"].get("swe"):
            data_groups["swe"] = metadata["groups"]["swe"]
    
        if metadata["groups"].get("precip"):
            data_groups["precip"] = metadata["groups"]["precip"]

        # reorder list so the chart traces are in correct order
        if 'Storage (ac-ft)' in data_groups["storage"]:
            data_groups["storage"].insert(0, data_groups["storage"].pop(data_groups["storage"].index('Storage (ac-ft)')))

        if 'Gross Pool' in data_groups["storage"]:
            data_groups["storage"].insert(0, data_groups["storage"].pop(data_groups["storage"].index('Gross Pool')))

        if 'Top of Conservation (ac-ft)' in data_groups["storage"]:
            data_groups["storage"].insert(0, data_groups["storage"].pop(data_groups["storage"].index('Top of Conservation (ac-ft)')))

        if 'Top of Conservation High (ac-ft)' in data_groups["storage"]:
            data_groups["storage"].insert(0, data_groups["storage"].pop(data_groups["storage"].index('Top of Conservation High (ac-ft)')))

        return_obj['data_groups'] = data_groups
        return_obj['ymarkers'] = metadata["ymarkers"]
        return_obj['title'] = f"{metadata['title']}<br>WY {self.year} | Generated: {metadata['generated']}"
            
        return return_obj
    
    
    def get_usace_plot_data(self, time_period="h", metadata=False):
        print("Getting CWMS Metadata")
        data_type = "meta" if metadata else "plot"
        meta_url = f"https://www.spk-wc.usace.army.mil/fcgi-bin/compressed.py?href=/plots/csv/{self.location}{time_period}_{self.year}.{data_type}"  # noqa: E501
        res = requests.get(meta_url, verify=False)
    
        if res.status_code == 404:
            return None
        else:
            return res
    
    def get_plot_series(self):    
        series = []

        for column_name in self.data_groups.get('storage', []):
            sub_df = self.time_series_data[[column_name, "Datetime"]].dropna(how="any")
            valid_dates = sub_df["Datetime"].dt.strftime("%Y-%m-%dT%H").tolist()
            
            if "Storage" in column_name:
                plot_color = "rgb(8, 48, 255)"
            elif "Gross Pool" in column_name:
                plot_color = "rgb(31, 113, 181)"
            elif "Conservation High" in column_name:
                plot_color = "rgb(211, 211, 211)"
            elif "Conservation" in column_name:
                plot_color = "rgb(146, 197, 222)"
            else:
                plot_color = None

            series.append(go.Scatter(
                mode= "lines+markers" if "Conservation" in column_name else "lines",
                name= column_name,
                x= valid_dates,
                y= sub_df[column_name].astype(float).round(2).tolist(),
                yaxis= "y2",
                legend= "legend2",
                legendgroup= "legend2",
                fill= "tozeroy" if "Conservation" in column_name else None,
                fillcolor= plot_color,
                marker= {
                    "symbol": "triangle-down" if "Conservation" in column_name else None,
                },
                line= {
                    "color": plot_color,
                    "dash": "dot" if "Gross Pool" in column_name else "solid",
                }
            ))

        for column_name in self.data_groups.get('elevation', []):
            sub_df = self.time_series_data[[column_name, "Datetime"]].dropna(how="any")
            valid_dates = sub_df["Datetime"].dt.strftime("%Y-%m-%dT%H").tolist()

            series.append(go.Scatter(
                mode= "none",
                name= column_name,
                x= valid_dates,
                y= sub_df[column_name].tolist(),
                yaxis= "y4",
                showlegend= False
            ))

        for column_name in self.data_groups.get('flow', []):
            sub_df = self.time_series_data[[column_name, "Datetime"]].dropna(how="any")
            valid_dates = sub_df["Datetime"].dt.strftime("%Y-%m-%dT%H").tolist()
            
            if "Inflow" in column_name:
                plot_color = "rgb(27, 158, 119)"
            elif "Outflow" in column_name:
                plot_color = "rgb(217, 95, 2)"
            else:
                plot_color = None

            series.append(go.Scatter(
                mode= "lines",
                name= column_name,
                x= valid_dates,
                y= sub_df[column_name].tolist(),
                line= {
                    "color": plot_color,
                    "dash": "solid" if plot_color else "dot",
                },
                legend= "legend3",
                legendgroup= "legend3",
                    ))

        for column_name in self.data_groups.get('precip', []):
            sub_df = self.time_series_data[[column_name, "Datetime"]].dropna(how="any")
            valid_dates = sub_df["Datetime"].dt.strftime("%Y-%m-%dT%H").tolist()

            series.append(go.Bar(
                name= column_name,
                x= valid_dates,
                y= sub_df[column_name].tolist(),
                yaxis= "y3",
                marker= {"color": "blue"},
                legend= "legend",
                legendgroup= "legend",
                    ))

        for column_name in self.data_groups.get('swe', []):
            sub_df = self.time_series_data[[column_name, "Datetime"]].dropna(how="any")
            valid_dates = sub_df["Datetime"].dt.strftime("%Y-%m-%dT%H").tolist()

            series.append(go.Scatter(
                mode= "lines",
                name= column_name,
                x= valid_dates,
                y= sub_df[column_name].tolist(),
                yaxis= "y5",
                fill= "tozeroy",
                fillcolor= "rgb(8, 48, 107)",
                line= {
                    "color": "rgb(51, 51, 51)",
                },
                legend= "legend4",
                legendgroup= "legend4",
                    ))
    
        self.plot_series = series
    
        return
    
    def get_plot_layout(self):  
        shapes = []
            
        
        layout = go.Layout(
            title= self.title,
            autosize= True,
            xaxis= {
              "autorange": True,
              "rangeselector": {
                "buttons": [
                  { "step": "all" },
                  {
                    "count": 6,
                    "label": "6m",
                    "step": "month",
                    "stepmode": "backward",
                  },
                  {
                    "count": 1,
                    "label": "1m",
                    "step": "month",
                    "stepmode": "backward",
                  },
                  {
                    "count": 7,
                    "label": "1w",
                    "step": "day",
                    "stepmode": "backward",
                  },
                  {
                    "count": 3,
                    "label": "3d",
                    "step": "day",
                    "stepmode": "backward",
                  },
                  {
                    "count": 12,
                    "label": "12h",
                    "step": "hour",
                    "stepmode": "backward",
                  },
                ],
              },
              "type": "date",
            },
            yaxis= {
              "type": "linear",
              "domain": [0, 0.5],
              "title": "Flow<br>(cfs)",
            },
            yaxis2= {
              "domain": [0.5, 1],
              "title": "Storage<br>(ac-ft)",
            },
            yaxis4= {
              "domain": [0.5, 1],
              "side": "right",
              "overlaying": "y2",
              "title": "Elevation<br>(ft)",
            },
            legend= {
              "title": "Precipitation",
              "xref": "container",
              "yref": "container",
              "y": 0.5,
              "x": 1.1,
              "groupclick": "toggleitem",
              "tracegroupgap": 30,
            },
            legend2= {
              "title": "Storage",
              "groupclick": "toggleitem",
            },
            legend3= {
              "title": "Flow",
              "groupclick": "toggleitem",
            },
            legend4= {
              "title": "SWE",
              "groupclick": "toggleitem",
            },
            hovermode= "x",
            hoversubplots= "axis",
            autotypenumbers="convert types"
        )

        if "precip" in self.data_groups or "swe" in self.data_groups:
            layout["yaxis"]["domain"] = [0, 0.33]
            layout["yaxis2"]["domain"] = [0.33, 0.66]
            layout["yaxis4"]["domain"] = [0.33, 0.66]

        if "precip" in self.data_groups:
            layout["yaxis3"] = {
              "autorange": "reversed",
              "domain": [0.66, 1],
              "title": "Precipitation<br>(in)",
            }

        if "swe" in self.data_groups:
            layout["yaxis5"] = {
                "domain": [0.66, 1],
                "title": "SWE<br>(in)",
                "side": "right",
            }

        if "precip" in self.data_groups and "swe" in self.data_groups:
            layout["yaxis3"]["domain"] = [0.66, 0.83]
            layout["yaxis5"]["domain"] = [0.83, 1]
            shapes.append({
                "type": "line",
                "xref": "paper",
                "yref": "paper",
                "x0": 0,
                "x1": 1,
                "y0": 0.83,
                "y1": 0.83,
            })
        
        yaxis_dividers = len(self.data_groups)
        if "storage" in self.data_groups and "elevation" in self.data_groups:
            yaxis_dividers -= 1
            
        if "precip" in self.data_groups and "swe" in self.data_groups:
            yaxis_dividers -= 1

        for yaxis_divider_idx in range(1, yaxis_dividers):
            shapeHeight = yaxis_divider_idx / yaxis_dividers;
            shapes.append({
                "type": "line",
                "xref": "paper",
                "yref": "paper",
                "x0": 0,
                "x1": 1,
                "y0": shapeHeight,
                "y1": shapeHeight,
            });


        layout['shapes'] = shapes
            
        self.layout = layout
    
        return