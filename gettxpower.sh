#!/bin/bash

function port_to_i2c(){
	# Function to translate from port number to i2c number
	# Port 1 is on i2c 17
	# Port 7 is on i2c 23.
	port_list=($(seq 16 1 50))
	# Plan is to use the number in the array as translation to the port.
	# Since the array starts with 0 we start the array with 16.
	# If port $1 is less than 1 and greater than 34 return first port.
	# echo $port_list
	number=$(($1+0))
	if [[ $number -gt 0 && $number -lt 35 ]];
	then
		echo ${port_list[$1]}
		return ${port_list[$1]}
	else
		echo "Port number is no good"
		exit
	fi
}

function dump_eeprom_page() {
	# Function to read the first page from a transceiver
	# $1 i2c port
	ret_port=$(port_to_i2c $1)
	dd if="/sys/bus/i2c/devices/${ret_port}-0050/eeprom" bs=1 count=256 status=none | hexdump -v -C
}

function get_relative_register (){
	#$1 is page in hex
	#$2 is register in dec according to cmis
	dec_val=$(hex_to_dec $1)
	page_val=$(($dec_val*128))
	page_reg_val=$(($page_val+$2))
	echo "$page_reg_val"
}

function get_page_address(){
	page_start=$(get_relative_register $1 128)
	echo $page_start
}

function dump_page(){
	# Function to read the upper 128 bytes of a page from a transceiver
	# $1 i2c port
	# $2 CMIS page in hex
	#echo "Port $1 Dumping Page $2"
	ret_port=$(port_to_i2c $1)
	ee_addr=$(get_relative_register $2 0)
	pg_addr=$(get_page_address $2)
	(dd if="/sys/bus/i2c/devices/${ret_port}-0050/eeprom" bs=128 count=1 status=none 
	dd if="/sys/bus/i2c/devices/${ret_port}-0050/eeprom" skip=$(( 10#$pg_addr )) bs=1 count=128 status=none) | hexdump -v -C
	# echo "$ee_addr"
}

dump_eeprom() {
	ret_port=$(port_to_i2c $1)
	cat "/sys/bus/i2c/devices/${ret_port}-0050/eeprom" | hexdump -v -C
}

function write_i2c(){
	# Function to write one byte in hex to a specific address in decimal.
	# $1 which port in dec
	# $2 which page in hex.
	# $3 what register in decimal.
	# $4 what value in hex 0x00-0xff to write with.
	# echo "Writing port:$1 page:$2 register:$3 value:$4"
	ret_port=$(port_to_i2c $1)
	rel_val=$(get_relative_register $2 $3)
	printf "$(printf '\\x%02X' $4)" | dd of=/sys/bus/i2c/devices/${ret_port}-0050/eeprom bs=1 seek=$(( 10#$rel_val )) count=1 conv=notrunc status=none
}

function read_eeprom_byte() {
	# Function to read one byte from
	# $1 port
	# $2 page
	# $3 register
	ret_port=$(port_to_i2c $1)
	rel_val=$(get_relative_register $2 $3)
	val_ret=$(dd if=/sys/bus/i2c/devices/${ret_port}-0050/eeprom bs=1 skip=$(( 10#$rel_val )) count=1 status=none | hexdump -v -e '16/1 "%02x " "\n"')
	echo $val_ret
}

function hex_to_dec (){
	# Function to translate from hexadecimal to decimal
	# $1 value in hex
	# echo ret_val in Dec
	echo $(( 16#$1 ))
}

function hex_to_dec_multi() {
	# Convert multiple bytes from hex to decimal
    	# $@ is the list of hex bytes (e.g., "0xA5" "0xC3")
    	local hex_string=""
    
    	# Loop through all arguments (hex bytes) and concatenate them
    	for byte in "$@"; do
        	# Remove the "0x" prefix from the hex byte
        	#hex_string+=$(echo $byte | sed 's/0x//')
		hex_string+=$(echo $byte | sed 's/^0x\|^[0-9A-Fa-f]x//')
    	done
    
    	# Convert the concatenated hex string to decimal
    	echo $((16#$hex_string))
}

#function works for current frequency
#hex_to_dec_multi 1x0b 5x63 0xf4 3x60
#hex_to_dec_multi 0x0b 0x90 0x34 0x80
#hex_to_dec_multi 0b 63 f4 60

# Read current frequency from EEPROM
function read_dec_multi_hex() {
	# Arguments:
    	# $1: port
	# $2: page
    	# $3: start register
    	# $4: stop register

	# Array to store hex values
    	local hex_values=()

    	# Read four bytes from consecutive registers (168, 169, 170, 171)
    	#for reg in {168..171}; do
	for (( reg=$3; reg<=$4; reg++ )); do
        	hex_value=$(read_eeprom_byte $1 $2 $reg)
        	hex_values+=("$hex_value")
    	done

    	# Print the read hex values
    	echo "Hex values: ${hex_values[*]}"

    	# Convert the hex values to decimal
    	current_freq=$(hex_to_dec_multi "${hex_values[@]}")

    	# Print the final decimal result
    	echo "Current Frequency (decimal): $current_freq"
}

#read current frequency, registers 168 to 171
#provide port number
#current frequency
#read_dec_multi_hex $1 12 168 171

#configured channel
#read_dec_multi_hex $1 12 136 137

# Function to convert multiple hex bytes to a signed decimal
function hex_to_signed_dec() {
	local divisor=$1
	shift  # Remove the divisor from the argument list

	local hex_string=""

    	# Loop through all arguments (hex bytes) and concatenate them
    	for byte in "$@"; do
        	# Remove any prefix like 0x, 1x, etc., if present
        	byte=$(echo "$byte" | sed 's/^[0-9a-fA-F]*x//')
        	# Concatenate the cleaned-up byte
        	hex_string+="$byte"
    	done

    	# Determine if the number is negative based on the most significant bit (MSB)
    	local first_byte=${hex_string:0:1}

    	# If the MSB is >= 8, treat it as a negative two's complement number
    	if [[ $((16#$first_byte)) -ge 8 ]]; then
        	# Extend the sign (pad with 'F's) to make it a negative number
        	local padded_hex=$(printf "%0${#hex_string}s" "$hex_string" | sed 's/ /F/g')
        	local signed_dec=$((16#$padded_hex))
        	# Adjust for two's complement
        	signed_dec=$((signed_dec - 2**(${#hex_string} * 4)))
    	else
        	# If positive, just convert it directly
        	signed_dec=$((16#$hex_string))
    	fi
	
	#divides the signed_dec by 100

    	echo "$signed_dec" | awk -v div=$divisor '{for(i=1; i<=NF; i++) printf "%.4f\n", $i/div}'

}

#hex_to_signed_dec 100 0xd9 0x54
#hex_to_signed_dec 100 0xfd 0x43
#hex_to_signed_dec 100 0xfb 0xc0
#hex_to_signed_dec 100 0xfd 0x29

function read_signed_dec_multi_hex() {
	# Arguments:
    	# $1: port
	# $2: page
    	# $3: start register
    	# $4: stop register
	# $5: divisor

	# Array to store hex values
    	local hex_values=()

    	# Read four bytes from consecutive registers (168, 169, 170, 171)
    	#for reg in {168..171}; do
	for (( reg=$3; reg<=$4; reg++ )); do
        	hex_value=$(read_eeprom_byte $1 $2 $reg)
		#echo $hex_value
        	hex_values+=("$hex_value")
    	done

    	# Print the read hex values
    	#echo "Hex values: ${hex_values[*]}"

    	# Convert the hex values to decimal
    	current_signed_dec=$(hex_to_signed_dec "$5" "${hex_values[@]}")

    	# Print the final decimal result
    	echo "$current_signed_dec"
}

#divisor:$5
#divisor is 100 for Tx and Rx power
#Tx power configured dBm
#read_signed_dec_multi_hex $1 11 154 155 100

#current Tx power dBm 
#read_signed_dec_multi_hex $1 27 128 129 100

#current Rx power dBm
#read_signed_dec_multi_hex $1 27 130 131 100

#current Rx power coherent
#read_signed_dec_multi_hex $1 27 132 133 100

#reads Rx power in mW
#divisor: $5 is 10000
#read_signed_dec_multi_hex $1 11 186 187 10000

function fast_read_rx(){
	#port: $1
	local rx_mw=$(read_signed_dec_multi_hex $1 11 186 187 10000)
	#echo "$rx_mw"
	#local rx_mw=0.0121
	result=$(awk -v rx="$rx_mw" 'BEGIN {print 10 * log(rx) / log(10)}')
	echo "$result"
}

function fast_read_tx(){
	#port: $1
	local tx_mw=$(read_signed_dec_multi_hex $1 11 154 155 10000)
	#echo "$rx_mw"
	#local rx_mw=0.0121
	result=$(awk -v tx="$tx_mw" 'BEGIN {print 10 * log(tx) / log(10)}')
	echo "$result"
}

fast_read_tx $1



#OSNR
#divisor is 10
#read_signed_dec_multi_hex $1 26 176 177 10

# Function to convert a single hex digit to a 4-bit binary string
function hex_digit_to_bin() {
	case "$1" in
        	0) echo "0000" ;;
        	1) echo "0001" ;;
        	2) echo "0010" ;;
        	3) echo "0011" ;;
        	4) echo "0100" ;;
        	5) echo "0101" ;;
       		6) echo "0110" ;;
        	7) echo "0111" ;;
        	8) echo "1000" ;;
        	9) echo "1001" ;;
        	A|a) echo "1010" ;;
        	B|b) echo "1011" ;;
        	C|c) echo "1100" ;;
        	D|d) echo "1101" ;;
        	E|e) echo "1110" ;;
        	F|f) echo "1111" ;;
        	*) echo "Invalid hex digit" ;;
    	esac
}

# Function to convert a hex byte (two hex digits) to an 8-bit binary string
function hex_byte_to_bin() {
    	#local hex_value="$1"
    	local hex_value="$(echo "$1" | sed 's/^[0-9a-fA-F]*x//')"
    	local bin_value=""

    	# Loop through each hex digit and convert it to binary
    	for (( i=0; i<${#hex_value}; i++ )); do
        	digit=${hex_value:$i:1}
        	bin_value+=$(hex_digit_to_bin "$digit")
    	done

    	# Check that the result is exactly 8 bits
    	if [ ${#bin_value} -ne 8 ]; then
        	echo "Error: Binary conversion should result in exactly 8 bits."
        	return 1
    	else
        	echo "$bin_value"
    	fi
}

#hex_byte_to_bin 0a 
#hex_byte_to_bin 01

# Function to convert a binary string to a decimal number
function bin_to_dec() {
    	local bin_value="$1"
    	echo $((2#$bin_value))
}

#bin_to_dec 00000001
#bin_to_dec 10000000

# Function to handle the Excel formula conversion logic for pre-FEC-BER values
# two hex numbers are retrieved from registrs
# function: 10^(BIN2DEC(HEX2BIN(FIRST 5 BITS HEX1))-24) * (BIN2DEC(HEX2BIN(LAST 3 BITS HEX1))*2^8+BIN2DEC(HEX2BIN(HEX2)))

function calculate_value() {
    	local hex1="$1"
    	local hex2="$2"

    	# Convert the first and second hex values to 8-bit binary strings
    	local bin1=$(hex_byte_to_bin "$hex1")
    	local bin2=$(hex_byte_to_bin "$hex2")

    	if [ $? -ne 0 ]; then
        	echo "Error in binary conversion"
        	return 1
    	fi

    	# Extract the first 5 bits of bin1 and convert to decimal
    	local bin1_first5=${bin1:0:5}
    	local dec_value_first5_bits_bin1=$(bin_to_dec "$bin1_first5")

    	# Extract the last 3 bits of bin1 and combine with bin2 to form the second decimal value
    	local bin1_last3=${bin1:5:3}
    	local dec_value_last3_bits_bin1=$(bin_to_dec "$bin1_last3")

    	local bin2_dec=$(bin_to_dec "$bin2")

    	# Calculate the exponent and result according to the Excel formula
    	local exponent=$((dec_value_first5_bits_bin1 - 24))
    	local multiplication=$((dec_value_last3_bits_bin1 * 256))

    	# Check if the exponent is negative
    	if (( exponent < 0 )); then
        	# Use awk to calculate 10 raised to the negative exponent
        	power_of_ten=$(awk "BEGIN { print 10^($exponent) }")
   	else
        	# Use bash arithmetic for positive exponents
        	power_of_ten=$((10 ** exponent))
    	fi

    	# Calculate the final result
    	local addition=$(awk "BEGIN { print $multiplication + $bin2_dec }")
    	final_result=$(awk "BEGIN { print $power_of_ten * $addition }")

    	# Output the final result
    	echo "$final_result"
}

#calculate_value a0 e5
#calculate_value d8 70
#calculate_value 0x99 0xc3
#calculate_value 0x99 0xb0

function read_pre_fec_ber() {
    # Arguments:
    # $1: port
    # $2: page
    # $3: start register
    # $4: stop register

    # Array to store hex values
    local hex_values=()

    # Read the hex values from the specified register range
    for (( reg=$3; reg<=$4; reg++ )); do
        hex_value=$(read_eeprom_byte "$1" "$2" "$reg")
        hex_values+=("$hex_value")
    done

    # Check if we have an even number of hex values for pairing
    local hex_count=${#hex_values[@]}
    if (( hex_count % 2 != 0 )); then
        echo "Error: Odd number of hex values read. Expected pairs."
        return 1
    fi

    # Loop through hex values in pairs and call calculate_value
    for (( i=0; i<hex_count; i+=2 )); do
        local hex1="${hex_values[i]}"
        local hex2="${hex_values[i+1]}"

        # Call the calculate_value function with the two hex values
        local result=$(calculate_value "$hex1" "$hex2")

        # Output the result for the pair
        echo "$result"
    done
}
#preFEC BER Media input DP1
#read_pre_fec_ber 1 24 134 135

#preFEC BER Media input DP2
#read_pre_fec_ber $1 24 150 151

#preFEC BER Media input DP3
#read_pre_fec_ber $1 24 166 167

#preFEC BER Media input DP4
#read_pre_fec_ber $1 24 182 183

#preFEC BER Media input DP5
#read_pre_fec_ber $1 24 198 199

#preFEC BER Media input DP6
#read_pre_fec_ber $1 24 214 215

#preFEC BER Media input DP7
#read_pre_fec_ber $1 24 230 231

#preFEC BER Media input DP8
#read_pre_fec_ber $1 24 246 247

function convert_to_twos_complement() {
    local n="$1"
    local bits=16  # Number of bits for representation

    # Get the absolute value
    local abs_value=$(( -n ))

    # Convert absolute value to binary using shell arithmetic
    local binary=""
    while [ "$abs_value" -gt 0 ]; do
        binary=$((abs_value % 2))$binary
        abs_value=$((abs_value / 2))
    done
    binary=$(printf "%0${bits}d" "$binary")  # Pad with leading zeros to 16 bits

    # Invert the bits using awk (for two's complement)
    local inverted_binary=$(echo "$binary" | awk -v bits="$bits" '{
        result = ""; 
        for(i=1; i<=bits; i++) {
            if(substr($0,i,1) == "0") {
                result = result "1";  
            } else {
                result = result "0";  
            }
        }
        print result;
    }')

    # Add 1 to the inverted binary
    local carry=1
    local twos_complement_binary=""
    for ((i=$bits; i>=1; i--)); do
        bit=$(echo "$inverted_binary" | cut -c "$i")
        if [[ $bit == 1 && $carry == 1 ]]; then
            twos_complement_binary="0$twos_complement_binary"
        elif [[ $bit == 0 && $carry == 1 ]]; then
            twos_complement_binary="1$twos_complement_binary"
            carry=0
        else
            twos_complement_binary="$bit$twos_complement_binary"
        fi
    done

    # Convert the binary to hex
    local hex_n_low=$(printf "%02X" $((2#${twos_complement_binary:0:8})))   # low byte (first 8 bits)
    local hex_n_high=$(printf "%02X" $((2#${twos_complement_binary:8:8})))    # high byte (last 8 bits)

    echo "$hex_n_low $hex_n_high"  # Return both bytes
}


#convert_to_twos_complement -96

function set_frequency() {
    # Arguments:
    # $1: port
    # $2: desired frequency (in THz)
    # $3: desired grid (can be 6.25, 75, or 100)

    # Validate the grid argument
    if [[ "$3" != "6.25" && "$3" != "75" && "$3" != "100" ]]; then
        echo "Error: Invalid grid value. Must be 6.25, 75, or 100."
        return 1
    fi

    # Read the current grid value from register 128
    local current_grid_value=$(read_eeprom_byte $1 12 128)

    # Check if the current grid value is valid
    if [[ ! "$current_grid_value" =~ ^[0-9]+$ ]]; then
        echo "Error: Invalid value read from register 128: $current_grid_value"
        return 1
    fi

    echo "Current Register Value: $current_grid_value"

    # Change the grid if the current value does not match the desired grid
    case "$3" in
        6.25)
            if [[ "$current_grid_value" -ne 10 ]]; then
                write_i2c $1 12 128 0x10
                echo "Changing grid to 6.25"
            fi
            ;;
        75)
            if [[ "$current_grid_value" -ne 70 ]]; then
                write_i2c $1 12 128 0x70
                echo "Changing grid to 75"
            fi
            ;;
        100)
            if [[ "$current_grid_value" -ne 50 ]]; then
                write_i2c $1 12 128 0x50
                echo "Changing grid to 100"
            fi
            ;;
    esac

    local n

    if awk "BEGIN {exit ($2 == 193.09375) ? 0 : 1}"; then
	    n=-1
	    echo $n frequency equal to 193.09375
    else
    	case "$3" in
       		6.25)
  	  		n=$(awk "BEGIN { printf int(($2 - 193.1) / 0.00625) }")
        		;;
       		75)
          		n=$(awk "BEGIN { print int(($2 - 193.1) / 0.025) }")
            		;;
        	100)
            		n=$(awk "BEGIN { print int(($2 - 193.1) / 0.1) }")
            		;;
    	esac
    fi

    #n=$(printf "%.0f" "$n")  # Round n to the nearest integer
    #echo "Calculated n: $n"
    
    if (( n >= 0 )); then
    	# For positive n, use the positive logic
    	local hex_n_low=$(printf "%02X" $((n >> 8)))   # High byte
    	local hex_n_high=$(printf "%02X" $((n & 0xFF)))  # Low byte
    else
    	if [ "$n" -eq -1 ] && awk "BEGIN {exit ($2 == 193.09375) ? 0 : 1}"; then
        	#echo "new n $n frequency $2" 
        	read hex_n_low hex_n_high < <(convert_to_twos_complement "$n")
    	else
        	n=$((n - 1))  # Decrease n by 1, rounding issue
        	read hex_n_low hex_n_high < <(convert_to_twos_complement "$n")
    	fi
     fi

    
    # Write the two bytes to the respective registers
    echo "Writing $hex_n_low to register 136 and $hex_n_high to register 137"
    write_i2c "$1" 12 136 "0x$hex_n_low"
    write_i2c "$1" 12 137 "0x$hex_n_high"
    
    echo "Frequency set successfully to $2 GHz with grid $3 GHz"

}
#set desired frequency port:$1, frequency:$2, grid:$3
#set_frequency $1 $2 $3

#read_signed_dec_multi_hex $1 12 136 137 1

#function to get configured frequency
function configured_frequency(){
	
	local current_grid_value=$(read_eeprom_byte $1 12 128)
	echo "$current_grid_value"
	local channel=$(read_signed_dec_multi_hex $1 12 136 137 1)
	echo "$channel"
	local configured_frequency
	case "$current_grid_value" in
       		10)
  	  		local grid=6.25
			echo $grid
			configured_frequency=$(awk "BEGIN { print 193.1 + $channel * 0.00625 }")
        		;;
       		70)
          		configured_frequency=$(awk "BEGIN { print 193.1 + $channel * 0.025 }")
            		;;
        	50)
            		configured_frequency=$(awk "BEGIN { print 193.1 + $channel * 0.1 }")
            		;;
    	esac

	echo "$configured_frequency"

}

#configured_frequency $1

function set_target_output_power_float() {
    local float_value="$2"
    #local float_value="$1"
    local n=$(awk "BEGIN { printf \"%d\", ($float_value * 100) }")  # Convert float to integer (multiplied by 100)

    if (( n >= 0 )); then
        # For positive n, calculate the high and low bytes
        local hex_n_high=$(printf "%02X" $((n & 0xFF)))   # Low byte
        local hex_n_low=$(printf "%02X" $((n >> 8)))    # High byte
    else
        # Convert negative n using two's complement
        read hex_n_low hex_n_high < <(dec_to_2_hex "$n")
    fi

    echo "Hex AA Low Byte: $hex_n_low"
    echo "Hex AA High Byte: $hex_n_high"

    # Optionally, write these to I2C if needed:
    write_i2c "$1" 12 200 "0x$hex_n_low"
    write_i2c "$1" 12 201 "0x$hex_n_high"
}

# Helper function to convert two's complement for negative integers
function dec_to_2_hex() {
    local n="$1"
    local bits=16  # Number of bits for representation

    if (( n < 0 )); then
        n=$(( (1 << bits) + n ))  # Two's complement conversion for negative numbers
    fi

    # Extract high and low bytes
    local hex_n_high=$(printf "%02X" $((n & 0xFF)))   # Low byte
    local hex_n_low=$(printf "%02X" $((n >> 8)))    # High byte

    echo "$hex_n_low $hex_n_high"
}


# Call the function with a float value, e.g., -7.01
#set_target_output_power_float $1 $2

function dec_to_1_or_2_hex(){
	local n="$1"

	local hex_n_low=$(printf "%02X" $((n >> 8)))   # Low byte
    	local hex_n_high=$(printf "%02X" $((n & 0xFF)))  # High byte

	if (( hex_n_low == 00)); then
		echo "$hex_n_low"
	else
		echo "$hex_n_low" "$hex_n_high"
	fi
}

#dec_to_1_or_2_hex 10
#dec_to_1_or_2_hex 210
#dec_to_1_or_2_hex 4090

#set_target_output_power_float $1 $2

