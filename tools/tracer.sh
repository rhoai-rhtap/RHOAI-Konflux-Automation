#!/bin/bash
export > /dev/null 2>&1

#quay RO token
#take rhoai version as input
#fetch latest image for given version
#nightly flag to pull nightly info
#take image as input as well
#print commits format
#print http format

RBC_REPO=https://github.com/red-hat-data-services/RHOAI-Build-Config
BUILD_TYPE=ci
IMAGE_TYPE=fbc
QUAY_BASE_URL="docker://quay.io/rhoai"
FBC_QUAY_REPO="rhoai-fbc-fragment"
BUNDLE_QUAY_REPO="odh-operator-bundle"
TAG=
DIGEST=
SHOW_COMMITS=
IMAGE=
CONFIGURE=
UPDATE=
IMAGE_URI=

POSITIONAL=()
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --rhoai-version | -v)
        TAG="$2"
        shift
        shift
        ;;
        --digest | -d)
        DIGEST="$2"
        shift
        shift
        ;;
        --nightly | -n)
        BUILD_TYPE=nightly
        shift
        ;;
        --show-commits | -c)
        SHOW_COMMITS=true
        shift
        shift
        ;;
        --image-type | -it)
        IMAGE_TYPE="$2"
        shift
        shift
        ;;
        --image | -i)
        IMAGE="$2"
        shift
        shift
        ;;
        configure)
        CONFIGURE=true
        shift
        shift
        ;;
        update)
        UPDATE=true
        shift
        shift
        ;;
        *)
        echo -n "Invalid arguments, please check the usage doc"
        exit 1
        ;;
    esac
done

if [[ $CONFIGURE == "true" ]]
then
  auth=$(cat ~/.ssh/.rhoai_quay_ro_token | base64 -d)
  IFS=':' read -a parts <<< "$auth"
  skopeo login -u "${parts[0]}" -p "${parts[1]}" quay.io/rhoai
  exit
fi

if [[ -z $TAG ]]; then TAG=$(git ls-remote --heads $RBC_REPO | grep 'rhoai' | awk -F'/' '{print $NF}' | sort -V | tail -1); fi
if [[ -z $IMAGE ]]
then
  IMAGE_TYPE=$(echo $IMAGE_TYPE | tr '[a-z]' '[A-Z]')
  BUILD_TYPE=$(echo $BUILD_TYPE | tr '[a-z]' '[A-Z]')
  IMAGE_MANIFEST=
  QUAY_REPO=

  if [[ -n $DIGEST ]]
  then
    if [[ "$DIGEST" != "sha256*" ]]; then DIGEST="sha256:${DIGEST}"; fi
    IMAGE_MANIFEST="@$DIGEST"
  elif [[ -n $TAG ]]
  then
    #TAG=$(echo $TAG | tr '[a-z]' '[A-Z]')
    if [[ "$TAG" == v* ]]; then TAG=$(echo $TAG | tr -d 'v'); fi
    if [[ "$TAG" != rhoai* ]]; then TAG="rhoai-${TAG}"; fi
    IMAGE_MANIFEST=":$TAG"
  fi
  if [[ $IMAGE_TYPE == "FBC" ]]; then QUAY_REPO=$FBC_QUAY_REPO; elif [[ $IMAGE_TYPE == "BUNDLE" ]]; then QUAY_REPO=$BUNDLE_QUAY_REPO; fi

  IMAGE_URI="${QUAY_BASE_URL}/${QUAY_REPO}${IMAGE_MANIFEST}"


else
  IMAGE_URI=$IMAGE
  if [[ "$IMAGE_URI" != docker* ]]; then IMAGE_URI="docker://${IMAGE}"; fi
fi

if [[ -n $IMAGE_URI ]]
  labels = $(skopeo inspect "${IMAGE_URI}" | jq .Labels)
