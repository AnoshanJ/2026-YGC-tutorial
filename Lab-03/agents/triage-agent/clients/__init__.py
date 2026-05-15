"""Mocked API clients for the Order Triage Crew.

Same isolation pattern as cs-agent: tools call into these clients so the mocks
can be swapped for real services without touching tool/agent code.
"""
