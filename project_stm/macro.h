#define	Macro_Set_Bit(dest, pos)				    ((dest) |=  ((unsigned)0x1<<(pos)))
#define	Macro_Clear_Bit(dest, pos)					((dest) &= ~((unsigned)0x1<<(pos)))
#define	Macro_Invert_Bit(dest, pos)				    ((dest) ^=  ((unsigned)0x1<<(pos)))

#define	Macro_Clear_Area(dest, bits, pos)			((dest) &= ~(((unsigned)bits)<<(pos)))
#define	Macro_Set_Area(dest, bits, pos)			    ((dest) |=  (((unsigned)bits)<<(pos)))
#define	Macro_Invert_Area(dest, bits, pos)			((dest) ^=  (((unsigned)bits)<<(pos)))

#define	Macro_Write_Block(dest, bits, data, pos)	((dest) = (((unsigned)dest) & ~(((unsigned)bits)<<(pos))) | (((unsigned)data)<<(pos)))
#define Macro_Extract_Area(dest, bits, pos)		    ((((unsigned)dest)>>(pos)) & (bits))

#define Macro_Check_Bit_Set(dest, pos)				((((unsigned)dest)>>(pos)) & 0x1)
#define Macro_Check_Bit_Clear(dest, pos)			(!((((unsigned)dest)>>(pos)) & 0x1))
