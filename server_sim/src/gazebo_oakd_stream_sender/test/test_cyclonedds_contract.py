import pathlib
import xml.etree.ElementTree as ET


def test_sender_uses_only_supported_jazzy_elements():
    config = pathlib.Path(__file__).parents[1] / 'config' / 'cyclonedds.xml'
    root = ET.parse(config).getroot()
    namespace = {'c': 'https://cdds.io/config'}

    assert root.find('./c:Domain/c:Channels', namespace) is None
    max_message = root.findtext(
        './c:Domain/c:General/c:MaxMessageSize', namespaces=namespace)
    fragment = root.findtext(
        './c:Domain/c:General/c:FragmentSize', namespaces=namespace)

    assert max_message == '1472B'
    assert fragment == '1344B'


def test_sender_has_no_hard_coded_peer():
    config = pathlib.Path(__file__).parents[1] / 'config' / 'cyclonedds.xml'
    root = ET.parse(config).getroot()
    namespace = {'c': 'https://cdds.io/config'}

    assert root.find('.//c:Peer', namespace) is None
