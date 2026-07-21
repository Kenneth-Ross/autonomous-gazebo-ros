import ipaddress
import json
import os
import subprocess


def parse_bool(value):
    if str(value).lower() not in ('true', 'false'):
        raise ValueError(f"expected true or false, got {value!r}")
    return str(value).lower() == 'true'


def validate_flags(enable_slam, enable_npu, enable_landmarks):
    if enable_landmarks and not enable_npu:
        raise ValueError('enable_landmarks requires enable_npu')
    if enable_landmarks and not enable_slam:
        raise ValueError('enable_landmarks requires enable_slam')


def validate_npu_model(enable_npu, model_path, exists=os.path.isfile):
    if enable_npu and not model_path:
        raise ValueError('enable_npu requires npu_model_path')
    if enable_npu and not exists(model_path):
        raise ValueError(f'NPU model does not exist: {model_path}')


def validate_network(interface, local_address, peer_address, inventory=None):
    ipaddress.ip_address(peer_address)
    if not interface:
        if local_address:
            raise ValueError('local_address requires network_interface')
        return
    if inventory is None:
        if not os.path.isdir(f'/sys/class/net/{interface}'):
            raise ValueError(f'network interface does not exist: {interface}')
        result = subprocess.run(
            ['ip', '-j', 'address', 'show', 'dev', interface], check=True,
            capture_output=True, text=True)
        inventory = json.loads(result.stdout)
    addresses = {
        item['local'] for device in inventory for item in device.get('addr_info', [])}
    if local_address and local_address not in addresses:
        raise ValueError(f'{local_address} is not assigned to {interface}')


def cyclone_uri(interface, local_address, peer_address):
    interface_xml = ''
    if interface:
        address = f' address="{local_address}"' if local_address else ''
        interface_xml = f'<Interfaces><NetworkInterface name="{interface}"{address}/></Interfaces>'
    return f'''<CycloneDDS xmlns="https://cdds.io/config"><Domain id="any"><General>
      {interface_xml}<MaxMessageSize>1472B</MaxMessageSize><FragmentSize>1344B</FragmentSize>
      <AllowMulticast>spdp</AllowMulticast></General><Internal>
      <SocketReceiveBufferSize min="10MB"/><SocketSendBufferSize min="10MB"/></Internal>
      <Discovery><Peers><Peer address="{peer_address}"/></Peers></Discovery>
      </Domain></CycloneDDS>'''
