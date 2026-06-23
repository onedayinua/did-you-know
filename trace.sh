#!/bin/bash

# Define the VPS list as a space-separated string block: "Name Hostname"
# This avoids using Bash 4+ associative arrays entirely.
vps_list="
Vultr_NJ nj-us-ping.vultr.com
Vultr_LA lax-ca-us-ping.vultr.com
Vultr_Dallas tx-us-ping.vultr.com
DO_NYC1 speedtest-nyc1.digitalocean.com
DO_SFO2 speedtest-sfo2.digitalocean.com
DO_NYC3 speedtest-nyc3.digitalocean.com
Linode_Newark speedtest.newark.linode.com
Linode_Fremont speedtest.fremont.linode.com
Linode_Dallas speedtest.dallas.linode.com
Linode_Atlanta speedtest.atlanta.linode.com
Hetzner_Ashburn ash.icmp.hetzner.com
Hetzner_Hillsboro hil.icmp.hetzner.com
RackNerd_LA lg-lax02.racknerd.com
RackNerd_NY lg-ny.racknerd.com
RackNerd_Chicago lg-chi.racknerd.com
BuyVM_LasVegas lv.buyvm.net
BuyVM_NewYork nj.buyvm.net
BuyVM_Miami mia.buyvm.net
HostHatch_LA la.hosthatch.com
HostHatch_Chicago chi.hosthatch.com
HostHatch_NY ny.hosthatch.com
VirMach_LA lax.lg.virmach.com
VirMach_Buffalo buf.lg.virmach.com
VirMach_Dallas dal.lg.virmach.com
RamNode_NY lg.nyc.ramnode.com
RamNode_LA lg.la.ramnode.com
RamNode_Atlanta lg.atl.ramnode.com
RamNode_Seattle lg.sea.ramnode.com
AlphaVPS_LA lg-la.alphavps.com
ExtraVM_Dallas dal.lg.extravm.com
"

results_file="vps_traceroute_results.txt"
> "$results_file"

echo "Tracing 30 US VPS locations. This may take a few minutes..."
echo "------------------------------------------------------------"

# Read the data line by line safely across any shell environment
echo "$vps_list" | sed '/^\s*$/d' | while read -r name host; do
    [ -z "$name" ] && continue
    echo -n "Tracing $name ($host)... "
    
    # Run traceroute: max 25 hops (-m), 2 probes (-q) to speed it up, 1s timeout (-w)
    # Redirecting both stdout and stderr allows us to handle missing command or bad host errors.
    output=$(traceroute -w 1 -q 2 -m 25 "$host" 2>/dev/null)
    
    # Handle absolute failure or complete network timeout (no successful ms returned)
    if [ $? -ne 0 ] || ! echo "$output" | grep -q "ms"; then
        echo "Timeout / Unreachable"
        time="9999"
    else
        # Extract the last successful hop that returned a response time
        last_hop=$(echo "$output" | grep "ms" | tail -n 1)
        
        # Calculate average ms from the probe values returned on that hop
        time=$(echo "$last_hop" | grep -oE '[0-9.]+ ms' | awk '{sum+=$1; count++} END {if(count>0) printf "%.2f", sum/count; else print "9999"}')
        
        if [ "$time" = "9999" ]; then
            echo "Timeout on final hop"
        else
            echo "${time} ms"
        fi
    fi
    
    # Save results for sorting
    echo "$time $name" >> "$results_file"
done

echo ""
echo "=== Top 5 Fastest VPS (Average Latency) ==="
# Sort numerically, filter out the 9999 placeholders, and present the top 5
sort -n "$results_file" | grep -v "9999" | head -n 5 | awk '{printf "%d. %-20s - %s ms\n", NR, $2, $1}'

# Clean up temporary results file
rm -f "$results_file"