"""Metrics pipeline: PLAN.md Section 4, one module per stat family.

Each submodule takes typed `war.records.Battle` rows and produces one stat
family per general. Kept as separate small modules (rather than one big
metrics.py) per CLAUDE.md's file-size guidance.
"""
