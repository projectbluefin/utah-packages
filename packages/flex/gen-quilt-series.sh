#!/bin/bash
# Autogenerates the quilt `series` from the patch order in the spec file.
# We don't use `quilt setup` because it makes a huge mess and doesn't work.
component="flex"
rm -f series.new
extra_args="--fuzz=0"
count=0
# Filter out the patches, and use `_` as our pseudo-IFS to prevent expansion.
for i in `grep '^%patch' flex.spec | sed -e 's,%patch,,g' -e 's, ,_,g'`; do
    # Split the patch into number and arguments.
    # 1 - Patch number.
    # 2-N - Patch arguments.
    # Get back our elements by undoing pseudo-IFS change.
    elements=(`echo $i | sed -e 's,_, ,g'`)
    num=${elements[0]}
    args=${elements[@]:1}
    # Find the next patch that applies in order and write it out.
    # This way we transform the patch # list into a patch file list in order.
    grep "Patch${num}: " flex.spec \
	| sed -e 's,Patch.*: ,,g' -e "s,\$, ${args[@]} ${extra_args},g" \
	| sed -e "s,%{name},${component},g" \
	>> series.new
    ((count++))
done
# Double check we processed the correct number of patches.
fcount=`wc -l series.new | sed -e 's, .*$,,g'`
if [ $fcount -ne $count ]; then
    echo "Error! Processed patch count doesn't match spec file count ($fcount != $count)."
    exit 1
fi
echo "Processed $count patches."
mv series.new series
echo "Generated quilt ./series file. Please do not commit."
exit 0
