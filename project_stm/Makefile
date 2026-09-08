# Tool information
ifeq ($(OS),Windows_NT)
    TOOL_DIR		?= C:/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi
    PROGRAMMER		?= STM32_Programmer_CLI.exe
else
    # Linux (Jetson / Ubuntu)
    TOOL_DIR		?= /home/aidl/toolchain
    PROGRAMMER		?= STM32_Programmer_CLI
endif

VERSION			= 15.2.1
TARGET			= arm-none-eabi

# Project name & Link script
OUT_FILE_NAME 	= rom_0x08000000
LDS_FILE_NAME	= rom_0x08000000.lds

# Compiler & Linker Option, Cortex-M4 & FPU hard
CFLAGS  		= -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -DSTM32F411xE 
CFLAGS 			+= -std=gnu99 -O3 -Wall -g -c -fno-builtin -funsigned-char -fno-strict-aliasing -fno-common
LDFLAGS 		= -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
LDFLAGS    		+= --specs=nano.specs --specs=nosys.specs -u _printf_float -nostartfiles -ffreestanding
LDFLAGS    		+= -Wl,-Map=$(OUT_FILE_NAME).map -Wl,--cref -Wl,-EL -T $(LDS_FILE_NAME)

# Output File definition
OUT_BIN_FILE	= $(OUT_FILE_NAME).bin
OUT_ELF_FILE	= $(OUT_FILE_NAME).elf
OUT_MAP_FILE	= $(OUT_FILE_NAME).map
OUT_DUMP_FILE	= $(OUT_FILE_NAME).dmp

# Tool setting
AS				= $(TOOL_DIR)/bin/$(TARGET)-as
CC				= $(TOOL_DIR)/bin/$(TARGET)-gcc
LD 				= $(TOOL_DIR)/bin/$(TARGET)-ld
OBJCOPY			= $(TOOL_DIR)/bin/$(TARGET)-objcopy
OBJDUMP			= $(TOOL_DIR)/bin/$(TARGET)-objdump

# Source & Header File 
CSRC 			= $(wildcard src/*.c)
ASRC 			= $(wildcard src/*.s)
HEADER 			= $(wildcard include/*.h)
OBJS    		= $(CSRC:.c=.o) $(ASRC:.s=.o)
DUMP 			= $(wildcard *.txt)

# Library and include folder
C_DIR			= $(TOOL_DIR)/$(TARGET)
GCC_DIR			= $(TOOL_DIR)/lib/gcc/$(TARGET)/$(VERSION)
LIB_OPTION		= -lc -lgcc
INCLUDE			= -nostdinc -Iinclude -I "$(C_DIR)/include" -I "$(GCC_DIR)/include" 

all : $(OUT_BIN_FILE)

$(OUT_BIN_FILE): $(OUT_ELF_FILE)
	$(OBJCOPY) $(OUT_ELF_FILE) $(OUT_BIN_FILE) -O binary
	$(OBJDUMP) -x -D ./$(OUT_ELF_FILE) > ./__dump.txt
	$(OBJDUMP) -x -D -S ./$(OUT_ELF_FILE) > ./__dump_all.txt

$(OUT_FILE_NAME).elf: $(OBJS)
	$(CC) $(OBJS) $(LDFLAGS) $(LIB_OPTION) -o $@

src/%.o: src/%.c $(HEADER)
	$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@

src/%.o: src/%.s $(HEADER)
	$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@

clean :
	rm -f $(OUT_BIN_FILE)
	rm -f $(OUT_ELF_FILE)
	rm -f $(OUT_MAP_FILE)
	rm -f $(OBJS)
	rm -f *.o
	rm -f $(DUMP)

run: # Flash STM32
ifeq ($(OS),Windows_NT)
	STM32_Programmer_CLI.exe -c port=SWD -w ./$(OUT_ELF_FILE) -v -rst -q
else
	@if command -v st-flash >/dev/null 2>&1; then \
		echo "--> st-flash를 사용하여 STM32 플래싱 중..."; \
		st-flash --reset write $(OUT_BIN_FILE) 0x08000000; \
	elif command -v STM32_Programmer_CLI >/dev/null 2>&1; then \
		echo "--> STM32_Programmer_CLI를 사용하여 STM32 플래싱 중..."; \
		STM32_Programmer_CLI -c port=SWD -w ./$(OUT_ELF_FILE) -v -rst -q; \
	elif command -v openocd >/dev/null 2>&1; then \
		echo "--> OpenOCD를 사용하여 STM32 플래싱 중..."; \
		openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program $(OUT_ELF_FILE) verify reset exit"; \
	else \
		echo "========================================================="; \
		echo "[오류] STM32 플래시 도구가 설치되어 있지 않습니다."; \
		echo "Linux(Jetson)에서는 stlink-tools를 설치하세요:"; \
		echo "    sudo apt install -y stlink-tools"; \
		echo "설치 후 'make run'을 다시 실행하시면 바로 플래싱됩니다."; \
		echo "========================================================="; \
		exit 1; \
	fi
endif	