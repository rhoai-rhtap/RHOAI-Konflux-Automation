# import yaml
# import ruamel.yaml as ruyaml
# import os
# from ruamel.yaml.scalarstring import DoubleQuotedScalarString
#
# operands_map_path = '/home/dchouras/RHODS/DevOps/rhods-operator-RHDS/build/operands-map.yaml'
#
# latest_images = ruyaml.load(open(operands_map_path), Loader=ruyaml.RoundTripLoader, preserve_quotes=True)
#
# images = []
#
# keys = ['RELATED_IMAGE_ODH_OPERATOR_IMAGE']
# for index, image in enumerate(latest_images['relatedImages']):
#     if 'name' in image and image['name'] not in keys:
#         keys.append(image['name'])
#         images.append({'name': image['name'], 'value': image['value']})
#     else:
#         latest_images['relatedImages'].remove(image)
#
# ruyaml.dump(images, open('latest_images.yaml', 'w'), Dumper=ruyaml.RoundTripDumper,
#                     default_flow_style=False)
import yaml

# components = yaml.safe_load(open('bundle-patch-2.16.yaml'))
# open('poc.txt', 'w').write('nothing can beat python')
# print(list(set(open("latest_shipped_rhoai_versions.txt").readlines()) - set(open("shipped_rhoai_versions.txt").readlines())).__len__())







# bundle_csv_path = '/home/dchouras/RHODS/DevOps/FBC/rhoai-2.13/bundle/manifests/rhods-operator.clusterserviceversion.yml'
# output_file_path = 'output.yaml'
# import ruamel.yaml as yaml
#
# csv = yaml.load(open(bundle_csv_path), Loader=yaml.RoundTripLoader, preserve_quotes=True)
# env_list = csv['spec']['install']['spec']['deployments'][0]['spec']['template']['spec']['containers'][0][
#                 'env']
# env_list = [dict(item) for item in env_list]
# print(env_list)
# yaml.dump(csv, open(output_file_path, 'w'), Dumper=yaml.RoundTripDumper, default_flow_style=False)

# from ..quay_onboarder.quay_onboarder import quay_controller
# from ...utils.commons.quay_controller import quay_controller
# from utils.commons.quay_controller import quay_controller
# import yaml
# from ruamel.yaml.scalarstring import DoubleQuotedScalarString
# from bundle_processor import quay_controller
# build_config_path = '/home/dchouras/RHODS/DevOps/RHOAI-Build-Config/config/build-config.yaml'
# build_config = yaml.safe_load(open(build_config_path))
# qc  = quay_controller('rhoai')
# def get_all_latest_images_for_the_version(version:str):
#     latest_images = []
#     registry = 'quay.io'
#     for registry_entry in build_config['config']['replacements']:
#         registry = registry_entry['registry']
#         for repo_path in registry_entry['repo_mappings']:
#             # repo_path = 'rhoai/odh-dashboard-rhel8'
#             repo = '/'.join(repo_path.split('/')[1:])
#             tags = qc.get_all_tags(repo, version)
#             if not tags:
#                 print(f'no tags found for {repo}')
#             for tag in tags:
#                 sig_tag = f'{tag['manifest_digest'].replace(':', '-')}.sig'
#                 signature = qc.get_tag_details(repo, sig_tag)
#                 if signature:
#                     latest_images.append({'name': f'RELATED_IMAGE_{repo.replace("-rhel8", "").replace("-", "_").upper()}_IMAGE', 'value': DoubleQuotedScalarString(f'{registry}/{repo_path}@{tag["manifest_digest"]}')})
#                     break
#     print(latest_images)
#
#
#
# get_all_latest_images_for_the_version('rhoai-2.13')

# build_config_path = '/home/dchouras/RHODS/DevOps/RHOAI-Build-Config/config/build-config.yaml'
# import yaml
# config = yaml.safe_load(open(build_config_path))
# print(config['config']['replacements'][0]['registry'])
# count = 0
# for repo in config['config']['replacements'][0]['repo_mappings']:
#     count += 1
#     print(f'{repo.replace("rhoai/", "").replace("-rhel8", "")}-v2-13', end='\t')
# print(count)

from pathlib import Path
# abs='/home/dchouras/RHODS/DevOps/rhods-operator/Dockerfiles/bundle.Dockerfile'
# print(f'{Path(abs).parent.absolute()}')
#
# import os
# from pathlib import Path
# print(Path(os.path.abspath(__file__)).parent)
