import pytest
from rtabmap_bridge.launch_contract import cyclone_uri, validate_flags, validate_network


def test_invalid_flag_dependencies_are_rejected():
    with pytest.raises(ValueError): validate_flags(False, True, True)
    with pytest.raises(ValueError): validate_flags(True, False, True)
    validate_flags(False, False, False)


def test_dds_interface_address_and_peer_contract():
    inventory = [{'addr_info': [{'local': '10.10.12.11'}]}]
    validate_network('eth0', '10.10.12.11', '10.10.12.10', inventory)
    with pytest.raises(ValueError):
        validate_network('eth0', '10.10.12.99', '10.10.12.10', inventory)
    xml = cyclone_uri('eth0', '10.10.12.11', '10.10.12.10')
    assert 'name="eth0"' in xml and 'address="10.10.12.11"' in xml
