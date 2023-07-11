# Import the needed credential and management objects from the libraries.
import base64

from azure.identity import AzureCliCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

# Lire le contenu du fichier cloud-init.txt
with open('cloud-init.txt', 'r') as file:
    cloud_content = file.read()

# Encoder le contenu en base64
cloud_init = base64.b64encode(cloud_content.encode('utf-8')).decode('utf-8')

print(
    "Provisioning a virtual machine...some operations might take a \
minute or two."
)

# Acquire a credential object using CLI-based authentication.
credential = AzureCliCredential()

# Retrieve subscription ID from environment variable.
subscription_id = "ec907711-acd7-4191-9983-9577afbe3ce1"


# Step 1: Provision a resource group

# Obtain the management object for resources, using the credentials
# from the CLI login.
resource_client = ResourceManagementClient(credential, subscription_id)

# Constants we need in multiple places: the resource group name and
# the region in which we provision resources. You can change these
# values however you want.
RESOURCE_GROUP_NAME = "nginx-t0t0r-VM-rg"
LOCATION = "northeurope"

# Provision the resource group.
rg_result = resource_client.resource_groups.create_or_update(
    RESOURCE_GROUP_NAME, {"location": LOCATION}
)

print(
    f"Provisioned resource group {rg_result.name} in the \
{rg_result.location} region"
)

# For details on the previous code, see Example: Provision a resource
# group at https://learn.microsoft.com/azure/developer/python/
# azure-sdk-example-resource-group

# Step 2: provision a virtual network

# A virtual machine requires a network interface client (NIC). A NIC
# requires a virtual network and subnet along with an IP address.
# Therefore we must provision these downstream components first, then
# provision the NIC, after which we can provision the VM.

# Network and IP address names
VNET_NAME = "nginx-t0t0r-vnet"
SUBNET_NAME = "nginx-t0t0r-subnet"
IP_NAME = "nginx-t0t0r-ip"
IP_CONFIG_NAME = "nginx-t0t0r-ip-config"
NIC_NAME = "nginx-t0t0r-nic"

# Obtain the management object for networks
network_client = NetworkManagementClient(credential, subscription_id)

# Provision the virtual network and wait for completion
poller = network_client.virtual_networks.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    VNET_NAME,
    {
        "location": LOCATION,
        "address_space": {"address_prefixes": ["10.0.0.0/26"]},
    },
)

vnet_result = poller.result()

print(
    f"Provisioned virtual network {vnet_result.name} with address \
prefixes {vnet_result.address_space.address_prefixes}"
)


# Step 4: Provision an IP address and wait for completion
poller = network_client.public_ip_addresses.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    IP_NAME,
    {
        "location": LOCATION,
        "sku": {"name": "Standard"},
        "public_ip_allocation_method": "Static",
        "public_ip_address_version": "IPV4",
    },
)

ip_address_result = poller.result()

print(
    f"Provisioned public IP address {ip_address_result.name} \
with address {ip_address_result.ip_address}"
)


poller = network_client.network_security_groups.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    "nginx-t0t0r-nsg",
    {
        "location": LOCATION,
        "security_rules": [
            {
                "name": "AllowSSH",
                "protocol": "Tcp",
                "source_port_range": "*",
                "destination_port_range": "22",
                "source_address_prefix": "*",
                "destination_address_prefix": "*",
                "access": "Allow",
                "priority": 100,
                "direction": "Inbound",
            },
            {
                "name": "AllowHTTP",
                "protocol": "Tcp",
                "source_port_range": "*",
                "destination_port_range": "80",
                "source_address_prefix": "*",
                "destination_address_prefix": "*",
                "access": "Allow",
                "priority": 101,
                "direction": "Inbound",
            },
            {
                "name": "AllowHTTPS",
                "protocol": "Tcp",
                "source_port_range": "*",
                "destination_port_range": "443",
                "source_address_prefix": "*",
                "destination_address_prefix": "*",
                "access": "Allow",
                "priority": 102,
                "direction": "Inbound",
            },
        ],
    },
)
nsg_result = poller.result()
print(
    f"Provisioned virtual network security group {nsg_result.name}"
)


# Step 3: Provision the subnet and wait for completion
poller = network_client.subnets.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    VNET_NAME,
    SUBNET_NAME,
    {
        "address_prefix": "10.0.0.0/28",
        "network_security_group": {"id": nsg_result.id}
    }
)
subnet_result = poller.result()

print(
    f"Provisioned virtual subnet {subnet_result.name} with address \
prefix {subnet_result.address_prefix}"
)

# Step 5: Provision the network interface client
poller = network_client.network_interfaces.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    NIC_NAME,
    {
        "location": LOCATION,
        "ip_configurations": [
            {
                "name": IP_CONFIG_NAME,
                "subnet": {"id": subnet_result.id},
                "public_ip_address": {"id": ip_address_result.id},
            }
        ],
    },
)

nic_result = poller.result()

print(f"Provisioned network interface client {nic_result.name}")


# Step 6: Provision the virtual machine

# Obtain the management object for virtual machines
compute_client = ComputeManagementClient(credential, subscription_id)

VM_NAME = "nginx-t0t0r-VM"
USERNAME = "azureuser"
PASSWORD = "ChangePa$$w0rd24"

print(
    f"Provisioning virtual machine {VM_NAME}; this operation might \
take a few minutes."
)

# Provision the VM specifying only minimal arguments, which defaults
# to an Ubuntu 18.04 VM on a Standard DS1 v2 plan with a public IP address
# and a default virtual network/subnet.
cloud_init_content = '''#cloud-config
package_upgrade: true
runcmd:
  - sudo apt-get update
  - sudo apt-get install -y nginx
  - systemctl enable nginx
  - systemctl start nginx
users:
  - default
  - name: azureuser
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    lock_passwd: true
    ssh-authorized-keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDmvfnpYmM7+8qffubS89Ke2AcyqWvS7NDRmOGDaeBF/6KhVPZXxqGSToXOpEr3It0w+GUTra+FPEHDtNwo5tXhbsngIyT18E3xVF/Y4Qd8syyTvPyiOJz/AJoYm83v1LULFLtA9UmMPJuXdluqQFc5FF1aRNcvneDP2TxQfQ1R2qcIr2hDAOUN4FjJp9LKMWuRVTMP11oie4tYoLWI/qfkppUPoou9RE3+/LPdso7mpcmkrRSJGhTqRkGLkHpweEqDK1kzI1dPoWTaGrxy/xjGumWxhri2pVDpC9xXf9mWA7LRA730M18A2MEwbjj1OReVlaAcamOujTLxXBJtA1z7pPOb2/aK18no4IHks4xlONJuM0H+UyjGap05YEGGglCzl5ThJtter99SL4V0Q7d10iNNL/AfaBQ2y5b8sNM3JdjwKtkw8TC4BTEMkhEJwFFjngNJVvzzmLqQX2ytSn3CQ/Pqu8thDjTCW7rfrjDiBwG6/nhcsHdzJrmCS/Mp7pc= t0t0r@debian
'''


poller = compute_client.virtual_machines.begin_create_or_update(
    RESOURCE_GROUP_NAME,
    VM_NAME,
    {
        "location": LOCATION,
        "storage_profile": {
            "image_reference": {
                "publisher": "Canonical",
                "offer": "UbuntuServer",
                "sku": "18.04-LTS",
                "version": "latest",
            }
        },
        "hardware_profile": {"vm_size": "Standard_B1ls"},
        "os_profile": {
            "computer_name": VM_NAME,
            "admin_username": USERNAME,
            "admin_password": PASSWORD,
            "custom_data": base64.b64encode(cloud_init_content.encode('utf-8')).decode('utf-8'),
        },
        "network_profile": {
            "network_interfaces": [
                {
                    "id": nic_result.id,
                }
            ]
        },
    },
)

vm_result = poller.result()

print(f"Provisioned virtual machine {vm_result.name}")
