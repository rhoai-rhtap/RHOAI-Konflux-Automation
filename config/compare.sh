#!/bin/bash
releases=$(yq -o json releases.yaml)
releases=$(echo $releases | jq -r '.releases' | sed 's/ //g' | awk NF=NF RS= OFS=)
#ensure the nightlies are not triggered for any non-konflux version
min_release=217
filtered_releases=()
while IFS= read -r release
do
  version_number=${release/rhoai-/}
  version_number=${version_number/./}
  if [[ $version_number -ge $min_release ]]
  then
    filtered_releases+=("$release")
  fi
done < <(echo $releases | jq -r '.[]')
releases=$(jq -c -n '$ARGS.positional' --args "${filtered_releases[@]}" | sed 's/ //g' | awk NF=NF RS= OFS=)
echo "This job will trigger nightlies for: $releases"