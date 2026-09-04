MEMORY
{
	ROM  (rx) : ORIGIN = 0x08000000, LENGTH = 512K
	RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}

REGION_ALIAS("REGION_TEXT", ROM);
REGION_ALIAS("REGION_RODATA", ROM);
REGION_ALIAS("REGION_DATA", RAM);
REGION_ALIAS("REGION_BSS", RAM);

SECTIONS
{
	.text :
	{
		__RO_BASE__ = .;	
		crt0.o(.text)
		*(.text)
    	. = ALIGN(4); 
	} > REGION_TEXT

	.ARM.extab :
	{
		*(.ARM.extab* .gnu.linkonce.armextab.*)
		. = ALIGN(4); 
	} > REGION_RODATA

	.ARM.exidx :
	{
		*(.ARM.exidx* .gnu.linkonce.armexidx.*)
		. = ALIGN(4); 
	} > REGION_RODATA

	.rodata :
	{
		*(.rodata)
    	*(.rodata.*)
    	. = ALIGN(8); 
    	__RO_LIMIT__ = .;
	} > REGION_RODATA

	.data : AT(__RO_LIMIT__)
	{
		__RW_BASE__ = .;
		*(.data)
    	*(.data.*)
		. = ALIGN(4); 		
		__RW_LIMIT__ = .;			
	} > REGION_DATA
	
	__RW_SIZE__ = SIZEOF(.data);
	__RW_LOAD_ADDR__ = LOADADDR(.data);
	
	.bss :
	{
		__ZI_BASE__ = .;
		*(.bss)
    	*(.bss.*)		
		. = ALIGN(4); 		
		__ZI_LIMIT__ = .;
	} > REGION_BSS
	
	__ZI_SIZE__ = SIZEOF(.bss);	
}
