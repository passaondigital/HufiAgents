"""Additive V1.2 Work Evidence storage.

The table is independent of missions/tasks so evidence can also represent
company-level or routine activity.  Existing V1/V1.1 rows are untouched.
"""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    TABLES["work_evidence"].create(connection, checkfirst=True)
