"""Additive V1.2 Work Evidence storage."""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    TABLES["work_evidence"].create(connection, checkfirst=True)
