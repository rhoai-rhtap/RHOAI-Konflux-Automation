import os, requests
import time
import openshift_client as oc
from jsonupdate_ng import jsonupdate_ng
import argparse
import yaml
import ruamel.yaml as ruyaml
import json
from collections import defaultdict
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
import base64
import sys

print('OpenShift client version: {}'.format(oc.get_client_version()))

with oc.project('rhtap-releng-tenant'), oc.timeout(180 * 60):
    pr = 'managed-zfdwk'
    pr_object = oc.selector(f'pr/{pr}').object()
    status = pr_object.model.status.conditions[0].reason
    print(status)



