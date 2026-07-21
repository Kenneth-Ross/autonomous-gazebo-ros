import pathlib
import xml.etree.ElementTree as ET


def test_camera_channel_paces_new_and_auxiliary_traffic():
    config = pathlib.Path(__file__).parents[1] / 'config' / 'cyclonedds.xml'
    root = ET.parse(config).getroot()
    namespace = {'c': 'https://cdds.io/config'}
    channel = root.find('./c:Domain/c:Channels/c:Channel', namespace)

    assert channel is not None
    assert channel.attrib == {'Name': 'camera', 'TransportPriority': '0'}
    assert channel.findtext('c:DataBandwidthLimit', namespaces=namespace) == '180 Mbps'
    assert channel.findtext('c:AuxiliaryBandwidthLimit', namespaces=namespace) == '20 Mbps'


def test_sender_has_no_hard_coded_peer():
    config = pathlib.Path(__file__).parents[1] / 'config' / 'cyclonedds.xml'
    root = ET.parse(config).getroot()
    namespace = {'c': 'https://cdds.io/config'}

    assert root.find('.//c:Peer', namespace) is None
