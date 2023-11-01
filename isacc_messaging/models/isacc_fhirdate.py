"""ISACC FHIRDate Module

Captures common methods needed by ISACC for FHIRDate, by specializing
the `fhirclient.FHIRDate` class.
"""
from fhirclient.models.fhirdate import FHIRDate


class IsaccFHIRDate(FHIRDate):

    def __init__(self, jsonval=None):
        super(IsaccFHIRDate, self).__init__(jsonval=jsonval)

    def __gt__(self, other):
        return self.date > other.date

    def __eq__(self, other):
        if not other:
            return False
        if str(self) == str(other):
            return True

        # microseconds are not consistently handled by base FHIRDate class.
        # saved by some attributes, clipped by others.  see if values are
        # equal without microseconds, and consider it close enough
        self_wo_micros = self.date.replace(microsecond=0)
        other_dt = other.date if isinstance(other, FHIRDate) else other
        other_wo_micros = other_dt.replace(microsecond=0)
        return self_wo_micros.isoformat() == other_wo_micros.isoformat()

    def __repr__(self):
        """Use isoformat as default string representation"""
        return self.isostring


DEEP_PAST = IsaccFHIRDate("1975-01-01T00:00:00Z")
DEEP_FUTURE = IsaccFHIRDate("2025-01-01T00:00:00Z")
