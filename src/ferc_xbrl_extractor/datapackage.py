"""Define structures for creating a datapackage descriptor."""
import re
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import pydantic
import stringcase
from pydantic import BaseModel

from .helpers import get_logger
from .instance import Instance
from .taxonomy import Concept, LinkRole, Taxonomy


class Field(BaseModel):
    """
    A generic field descriptor, as per Frictionless Data specs.

    See https://specs.frictionlessdata.io/table-schema/#field-descriptors.
    """

    name: str
    title: str
    type_: str = pydantic.Field(alias="type", default="string")
    format_: str = pydantic.Field(alias="format", default="default")
    description: str

    @classmethod
    def from_concept(cls, concept: Concept) -> "Field":
        """Construct a Field from an XBRL Concept."""
        return cls(
            name=(concept.name),
            title=concept.standard_label,
            type=concept.type.get_schema_type(),
            description=concept.documentation,
        )


ENTITY_ID = Field(
    name="entity_id",
    title="Entity Identifier",
    type="string",
    description="Unique identifier of respondent",
)
"""
Field representing an entity ID (Present in all tables).
"""

FILING_NAME = Field(
    name="filing_name", title="Filing Name", type="string", description="Name of filing"
)
"""
Field representing the filing name (Present in all tables).
"""

START_DATE = Field(
    name="start_date",
    title="Start Date",
    type="date",
    description="Start date of report period",
)
"""
Field representing start date (Present in all duration tables).
"""

END_DATE = Field(
    name="end_date",
    title="End Date",
    type="date",
    description="End date of report period",
)
"""
Field representing end date (Present in all duration tables).
"""

INSTANT_DATE = Field(
    name="date", title="Instant Date", type="date", description="Date of instant period"
)
"""
Field representing an instant date (Present in all instant tables).
"""

DURATION_COLUMNS = [ENTITY_ID, FILING_NAME, START_DATE, END_DATE]
"""
Fields common to all duration tables.
"""

INSTANT_COLUMNS = [ENTITY_ID, FILING_NAME, INSTANT_DATE]
"""
Fields common to all instant tables.
"""


FIELD_TO_PANDAS: Dict[str, str] = {
    "string": "string",
    "number": "Float64",
    "integer": "Int64",
    "boolean": "boolean",
    "date": "string",
    "duration": "string",
    "year": "datetime64[ns]",
}
"""
Pandas data type by schema field type (Data Package `field.type`).
"""

CONVERT_DTYPES: Dict[str, Callable] = {
    "string": str,
    "integer": int,
    "year": int,
    "number": float,
    "boolean": bool,
    "duration": str,
    "date": str,
}
"""
Map callables to schema field type to convert parsed values (Data Package `field.type`).
"""

TABLE_NAME_PATTERN = re.compile("(.+) - Schedule - (.*)")  # noqa: W605, FS003
"""
Simple regex pattern used to clean up table names.
"""

UPPERCASE_WORD_PATTERN = re.compile("[^A-Z][A-Z]([A-Z]+)")
"""
Regex pattern to find fully uppercase words.

There are several tables in the FERC taxonomy that contain completely uppercase words,
which make converting to snakecase difficult.
"""


def _get_fields_from_concepts(
    concept: Concept, period_type: str
) -> Tuple[List[Field], List[Field]]:
    """
    Traverse concept tree to get columns and axes that will be used in output table.

    A 'fact table' in XBRL arranges Concepts into a a tree where the leaf nodes are
    individual facts that will become columns in the output tables. Axes are used to
    identify context of each fact, and will become a part of the primary key in the
    output table.

    Args:
        concept: The root concept of the tree.
        period_type: Period type of current table (only return columns with corresponding
                     period type).
    Returns:
        axes: Axes in table (become part of primary key).
        columns: List of fields in table.
    """
    axes = []
    columns = []
    for item in concept.child_concepts:
        if item.name.endswith("Axis"):
            axes.append(Field.from_concept(item))
        elif len(item.child_concepts) > 0:
            subtree_axes, subtree_columns = _get_fields_from_concepts(item, period_type)
            axes.extend(subtree_axes)
            columns.extend(subtree_columns)
        else:
            if item.period_type == period_type:
                columns.append(Field.from_concept(item))

    return axes, columns


def _lowercase_words(name: str) -> str:
    """
    Convert fully uppercase words so only first letter is uppercase.

    Pattern finds uppercase characters that are immediately preceded by
    an uppercase character. Later when the name is converted to snakecase,
    an underscore would be inserted between each of these charaters if this
    conversion is not performed.
    """
    matches = UPPERCASE_WORD_PATTERN.findall(name)
    for upper in matches:
        name = name.replace(upper, upper.lower())

    return name


def _clean_table_names(name: str) -> Optional[str]:
    """
    Function to clean table names.

    Args:
        name: Unprocessed table name.

    Returns:
        table_name: Cleaned table name or None if table name doesn't match expected
                    pattern.
    """
    name = _lowercase_words(name)
    m = TABLE_NAME_PATTERN.match(name)
    if not m:
        return None

    table_name = f"{m.group(2)}_{m.group(1)}"
    table_name = (
        table_name.replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace(".", "")
        .replace(",", "")
        .replace("/", "")
    )
    table_name = stringcase.snakecase(table_name)

    # The conversion to snakecase leaves some names with multiple underscores in a row
    table_name = table_name.replace("___", "_").replace("__", "_")

    return table_name


class Schema(BaseModel):
    """
    A generic table schema, as per Frictionless Data specs.

    See https://specs.frictionlessdata.io/table-schema/.
    """

    fields: List[Field]
    primary_key: List[str]

    @classmethod
    def from_concept_tree(cls, concept: Concept, period_type: str) -> "Schema":
        """
        Deduce schema from concept tree.

        Args:
            concept: Root concept of concept tree.
            period_type: Period type of table.
        """
        axes, columns = _get_fields_from_concepts(concept, period_type)
        if period_type == "duration":
            primary_key_columns = DURATION_COLUMNS + axes
        else:
            primary_key_columns = INSTANT_COLUMNS + axes

        fields = primary_key_columns + columns
        primary_key = [field.name for field in primary_key_columns]

        return cls(fields=fields, primary_key=primary_key)


class Dialect(BaseModel):
    """Dialect used for frictionless SQL resources."""

    table: str


class Resource(BaseModel):
    """
    A generic data resource, as per Frictionless Data specs.

    See https://specs.frictionlessdata.io/data-resource.
    """

    path: str
    profile: str = "tabular-data-resource"
    name: str
    dialect: Dialect
    title: str
    description: str
    format_: str = pydantic.Field(alias="sqlite", default="sqlite")
    mediatype: str = "application/vnd.sqlite3"
    encoding: str = "binary"
    schema_: Schema = pydantic.Field(alias="schema")

    @classmethod
    def from_link_role(
        cls, fact_table: LinkRole, period_type: str, db_path: str
    ) -> "Resource":
        """
        Generate a Resource from a fact table (defined by a LinkRole).

        Args:
            fact_table: Link role which defines a fact table.
            period_type: Period type of table.
        """
        cleaned_name = _clean_table_names(fact_table.definition)

        if not cleaned_name:
            return None

        name = f"{cleaned_name}_{period_type}"

        return cls(
            path=db_path,
            name=name,
            dialect=Dialect(table=name),
            title=f"{fact_table.definition} - {period_type}",
            description=fact_table.concepts.documentation,
            schema=Schema.from_concept_tree(fact_table.concepts, period_type),
        )

    def get_period_type(self):
        """Helper function to get period type from schema."""
        period_type = "instant" if "date" in self.schema_.primary_key else "duration"
        return period_type


class Datapackage(BaseModel):
    """
    A generic Data Package, as per Frictionless Data specs.

    See https://specs.frictionlessdata.io/data-package.
    """

    profile: str = "tabular-data-package"
    name: str = "ferc1-extracted-xbrl"
    title: str = "Ferc1 data extracted from XBRL filings"
    resources: List[Resource]

    @classmethod
    def from_taxonomy(cls, taxonomy: Taxonomy, db_path: str) -> "Datapackage":
        """
        Construct a Datapackage from an XBRL Taxonomy.

        Args:
            taxonomy: XBRL taxonomy which defines the structure of the database.
        """
        resources = []
        for role in taxonomy.roles:
            for period_type in ["duration", "instant"]:
                resource = Resource.from_link_role(role, period_type, db_path)
                if resource:
                    resources.append(resource)

        return cls(resources=resources)

    def get_fact_tables(self):
        """Get FactTables from datapackage."""
        return {
            resource.name: FactTable(resource.schema_, resource.get_period_type())
            for resource in self.resources
        }


class FactTable(object):
    """
    Class to handle constructing a dataframe from an XBRL fact table.

    Structure of the dataframe is defined by the XBRL taxonomy. Facts and contexts
    parsed from an individual XBRL filing are then used to populate the dataframe
    with relevant data.
    """

    def __init__(self, schema: Schema, period_type: str):
        """Create FactTable and prepare for constructing dataframe."""
        self.schema = schema
        # Map column names to function to convert parsed values
        self.columns = {
            field.name: CONVERT_DTYPES[field.type_] for field in schema.fields
        }
        self.axes = [name for name in schema.primary_key if name.endswith("Axis")]
        self.instant = period_type == "instant"
        self.logger = get_logger(__name__)

    def construct_dataframe(self, instance: Instance) -> pd.DataFrame:
        """
        Construct dataframe from a parsed XBRL instance.

        Args:
            instance: Parsed XBRL instance used to construct dataframe.
        """
        # Filter contexts to only those relevant to table
        contexts = instance.get_facts(self.instant, self.axes)

        # Get the maximum number of rows that could be in table and allocate space
        max_len = len(contexts)

        # Allocate space for columns
        df = {
            field.name: pd.Series([pd.NA] * max_len, dtype=FIELD_TO_PANDAS[field.type_])
            for field in self.schema.fields
        }

        # Loop through contexts and get facts in each context
        # Each context corresponds to one unique row
        for i, (context, facts) in enumerate(contexts.items()):
            if self.instant != context.period.instant:
                continue

            # Construct dictionary to represent row which corresponds to current context
            row = {fact.name: fact.value for fact in facts if fact.name in df}

            # If row is empty skip
            if row:
                # Use context to create primary key for row and add to dictionary
                row.update(context.as_primary_key(instance.filing_name))

                # Loop through each field in row and add to appropriate column
                for key, val in row.items():
                    # Try to parse value from XBRL if not possible it will remain NA
                    try:
                        df[key][i] = self.columns[key](val)
                    except ValueError:
                        self.logger.warning(
                            f"Could not parse {val} as {self.columns[key]} in column {key}"
                        )

        # Create dataframe and drop empty rows
        return pd.DataFrame(df).dropna(how="all")
