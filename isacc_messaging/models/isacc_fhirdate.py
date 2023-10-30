"""ISACC FHIRDate Module

Captures common methods needed by ISACC for FHIRDate, by specializing
the `fhirclient.FHIRDate` class.
"""
from fhirclient.models.fhirdate import FHIRDate


class IsaccFHIRDate(FHIRDate):

    def __init__(self, jsonval=None):
        super(IsaccFHIRDate, self).__init__(jsonval=jsonval)

    def __eq__(self, other: FHIRDate):
        if not other:
            return False
        if str(self) == str(other):
            return True

    def __repr__(self):
        """Use isoformat as default string representation"""
        return self.isostring


