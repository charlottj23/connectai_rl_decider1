import pytest

import connect_tycoon as ct


@pytest.fixture(scope="session")
def brain():
    return ct.CompanyBrain.default()


@pytest.fixture(scope="session")
def company(brain):
    return ct.Company(brain.intuition, ct.load_pool(), values=brain.values, rules=brain.rules)
