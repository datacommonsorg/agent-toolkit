# Copyright 2025 Google LLC.
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

# --- Imports ---
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, Field

# ==============================================================================
# 1. THE SINGLE, SIMPLE BASE CHART MODEL
# ==============================================================================


class BaseChart(BaseModel):
    """Contains fields required by ALL chart types."""

    header: str = Field(description="Title of the chart to be displayed.")


class SingleVariableChart(BaseChart):
    """Provides a single required 'variable' field."""

    variable_dcid: str = Field(
        description="DCID of a single statistical variable to display in the chart."
    )


class MultiVariableChart(BaseChart):
    """Provides a list of one or more 'variables'."""

    variable_dcids: list[str] = Field(
        description="List of DCIDs of statistical variables to display in the chart.",
        min_length=1,
    )


# ==============================================================================
# 2. LOCATION "BUILDING BLOCK" MODELS
# These are now the primary components for defining location information.
# ==============================================================================


class SinglePlaceLocation(BaseModel):
    """Defines a location using a specific list of places."""

    location_type: Literal["single_place"] = "single_place"
    place_dcid: str = Field(
        description="DCID of a single place to display statistical data for."
    )


class MultiPlaceLocation(BaseModel):
    """Defines a location using a specific list of places."""

    location_type: Literal["multi_place"] = "multi_place"
    place_dcids: list[str] = Field(
        description="List of place DCIDs to display statistical data for.", min_length=1
    )


class HierarchyLocation(BaseModel):
    """Defines a location using a parent/child hierarchy."""

    location_type: Literal["hierarchy"] = "hierarchy"
    parent_place_dcid: str = Field(
        description="DCID of a single place whose descendants should have statistical data displayed.",
    )
    child_place_type: str = Field(
        description="DCID of a valid child place type such as AdministrativeArea1 or County."
    )


# A discriminated union for charts that can accept either Places or Hierarchy
# location type (like BarChart).
LocationChoice = Annotated[
    (MultiPlaceLocation | HierarchyLocation), Field(discriminator="location_type")
]

# ==============================================================================
# 3. CONCRETE MODELS
# A single config representing a Data Commons web component.
#
# `location` is a field as opposed to extending a location class because some
#  charts like Bar and Line can have either MultiPlaceLocation OR HierarchyLocation
#  which means it shouldn't extend both classes. To keep location schema consistent
#  across all chart types, `location` is therefore a field.
# ==============================================================================


class BarChart(MultiVariableChart):
    type: Literal["bar"] = "bar"
    location: LocationChoice  # Either list or hierarchy


class LineChart(MultiVariableChart):
    type: Literal["line"] = "line"
    location: LocationChoice  # Either list or hierarchy


class RankingChart(MultiVariableChart):
    type: Literal["ranking"] = "ranking"
    location: HierarchyLocation


class ScatterChart(MultiVariableChart):
    """A Scatter Chart requires exactly two variables!"""

    type: Literal["scatter"] = "scatter"
    location: HierarchyLocation

    # OVERRIDE: A scatter plot requires exactly two variable DCIDs, one for each axis (x,y).
    variable_dcids: list[str] = Field(
        description="The two variable DCIDs to plot on x and y axes.",
        min_length=2,
        max_length=2,
    )


class PieChart(MultiVariableChart):
    type: Literal["pie"] = "pie"
    location: SinglePlaceLocation


class MapChart(SingleVariableChart):
    type: Literal["map"] = "map"
    location: HierarchyLocation


class GaugeChart(SingleVariableChart):
    type: Literal["gauge"] = "gauge"
    location: SinglePlaceLocation


class HighlightChart(SingleVariableChart):
    type: Literal["highlight"] = "highlight"
    location: SinglePlaceLocation


# ==============================================================================
# 4. FINAL DISCRIMINATED UNION OF ALL CHART TYPES
# ==============================================================================

# When adding a new chart type, add class name to this list.
DataCommonsChartUnion = (
    BarChart
    | GaugeChart
    | HighlightChart
    | LineChart
    | MapChart
    | PieChart
    | RankingChart
    | ScatterChart
)

DataCommonsChartConfig = Annotated[
    DataCommonsChartUnion,
    Field(discriminator="type"),
]

CHART_CONFIG_MAP = {
    get_args(ChartType.model_fields["type"].annotation)[0]: ChartType
    for ChartType in (get_args(DataCommonsChartUnion))
}
