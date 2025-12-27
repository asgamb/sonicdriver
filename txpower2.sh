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

function txpower(){
	# -7.0dBm => Reg. 200=0xFD Reg. 201=0x44
	write_i2c $1 12 200 0xFD
	write_i2c $1 12 201 0x44
	# Save persist
	write_i2c $1 b0 128 0x00
}

txpower $1
