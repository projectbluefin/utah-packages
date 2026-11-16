# Print the file a BuildStream element writes inline with a shell heredoc.
#
# Dakota elements write many small config files from install-commands:
#   cat > "%{install-root}.../60-kexec-disable.conf" <<'EOF'
#   kernel.kexec_load_disabled = 1
#   EOF
# Run with -v want=<target file name>, the element file as input. It finds
# the one `cat` heredoc whose target path ends in /<want>", and prints the
# heredoc body with the YAML block indentation (that of the `cat` line)
# removed, which is exactly what the shell writes. It fails unless exactly one
# heredoc matches and it is closed, so a renamed or restructured element
# breaks the build instead of shipping an empty or truncated file.
BEGIN { state = 0; found = 0 }

state == 0 && /cat/ && /<</ && index($0, "/" want "\"") {
    if (!match($0, /<<'?[A-Za-z_]+'?/)) {
        print "bst-heredoc: no heredoc delimiter on: " $0 > "/dev/stderr"
        exit 2
    }
    delim = substr($0, RSTART + 2, RLENGTH - 2)
    gsub(/'/, "", delim)
    match($0, /^ */)
    indent = RLENGTH
    state = 1
    found++
    next
}

state == 1 {
    line = $0
    trimmed = line
    sub(/^ +/, "", trimmed)
    if (trimmed == delim) {
        state = 0
        next
    }
    if (line ~ /^ *$/) {
        print ""
        next
    }
    if (substr(line, 1, indent) !~ /^ *$/) {
        print "bst-heredoc: line outside the block indentation: " line > "/dev/stderr"
        exit 2
    }
    print substr(line, indent + 1)
}

END {
    if (found != 1 || state != 0) {
        print "bst-heredoc: expected one closed heredoc writing " want ", found " found > "/dev/stderr"
        exit 1
    }
}
