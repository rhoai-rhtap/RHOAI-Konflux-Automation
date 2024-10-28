#!/bin/bash
export > /dev/null 2>&1

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
FULL_IMAGE_URI_WITH_DIGEST=
TEXT_OUTPUT=

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
        --bundle | -b)
        IMAGE_TYPE=bundle
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
    if [[ "$DIGEST" != sha256* ]]; then DIGEST="sha256:${DIGEST}"; fi
    IMAGE_MANIFEST="@$DIGEST"
  elif [[ -n $TAG ]]
  then
    #TAG=$(echo $TAG | tr '[a-z]' '[A-Z]')
    if [[ "$TAG" == v* ]]; then TAG=$(echo $TAG | tr -d 'v'); fi
    if [[ "$TAG" != rhoai* ]]; then TAG="rhoai-${TAG}"; fi
    if [[ "$BUILD_TYPE" == "NIGHTLY" ]]; then TAG="${TAG}-nightly"; echo $TAG; fi
    IMAGE_MANIFEST=":$TAG"
  fi
  if [[ $IMAGE_TYPE == "FBC" ]]; then QUAY_REPO=$FBC_QUAY_REPO; elif [[ $IMAGE_TYPE == "BUNDLE" ]]; then QUAY_REPO=$BUNDLE_QUAY_REPO; fi

  IMAGE_URI="${QUAY_BASE_URL}/${QUAY_REPO}${IMAGE_MANIFEST}"
  FULL_IMAGE_URI_WITH_DIGEST="${QUAY_BASE_URL}/${QUAY_REPO}"


else
  IMAGE_URI=${IMAGE/http:\/\//}
  IMAGE_URI=$(echo $IMAGE_URI | sed -e 's/:rhoai-2.*@/@/g')
  if [[ "$IMAGE_URI" != docker* ]]; then IMAGE_URI="docker://${IMAGE_URI}"; fi
  FULL_IMAGE_URI_WITH_DIGEST=$IMAGE_URI
fi

if [[ -n $IMAGE_URI ]]
then
  META=$(skopeo inspect "${IMAGE_URI}")
  NAME=$(echo $META | jq -r .Name)
  IFS='/' read -a parts <<< "$NAME"
  CURRENT_COMPONENT="${parts[2]}"
  DIGEST=$(echo $META | jq -r .Digest)

  labels=$(echo $META | jq .Labels)

  FULL_IMAGE_URI_WITH_DIGEST="${NAME}@${DIGEST}"
  BUILD_DATE=$(echo $labels | jq -r '."build-date"')

  TEXT_OUTPUT="${TEXT_OUTPUT}Image-URI ${FULL_IMAGE_URI_WITH_DIGEST}\n"
  TEXT_OUTPUT="${TEXT_OUTPUT}Build-Date ${BUILD_DATE}\n"

  if [[ "$SHOW_COMMITS" == "true" ]]
  then
    declare -a COMPONENTS=()
    while read -r key;
    do
      if [[ "$key" == *git.url ]]
      then
        if [[ $key == "git.url" ]]; then component="${CURRENT_COMPONENT}"; else component="${key/.git.url/}"; fi
        COMPONENTS+=($component)
      fi
      #echo $key=$(echo $labels | jq  --arg key "$key" -r '"\(.[$key])"')
    done < <(echo $labels | jq -r "keys[]")

    for component in "${COMPONENTS[@]}"
    do
      if [[ $component != "${CURRENT_COMPONENT}" ]]; then url_key="$component.git.url"; commit_key="$component.git.commit"; else url_key="git.url"; commit_key="git.commit"; fi
      URL=$(echo $labels | jq  --arg url_key "$url_key" -r '"\(.[$url_key])"')
      COMMIT=$(echo $labels | jq  --arg commit_key "$commit_key" -r '"\(.[$commit_key])"')

      TEXT_OUTPUT="${TEXT_OUTPUT}${component} ${URL}/tree/${COMMIT}\n"
    done
  fi
  echo -e "$TEXT_OUTPUT" | column -t

else
  echo "Image is not found"
fi