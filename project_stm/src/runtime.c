#include "device_driver.h"
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

char * _sbrk(int inc)
{
	extern unsigned char __ZI_LIMIT__;
	static char * heap = (char *)0;

	char * prevHeap;
	char * nextHeap;

	if(heap == (char *)0) heap = (char *)HEAP_BASE;

	prevHeap = heap;
	nextHeap = (char *)((((unsigned int)heap + inc) + 0x7) & ~0x7);

	if((unsigned int)nextHeap >= HEAP_LIMIT) return (char *)0;

	heap = nextHeap;
	return prevHeap;
}

int _write(int file, char *ptr, int len) 
{
    for (int i = 0; i < len; i++) 
	{
        Uart2_Send_Byte(*ptr++);
    }
    
	return len;
}

int _read(int file, char *ptr, int len) 
{ 
	return 0; 
}

int _lseek(int file, int ptr, int dir)  
{ 
	return 0; 
}

int _close(int file) 
{ 
	return -1; 
}

int _fstat(int file, struct stat *st) 
{
    st->st_mode = S_IFCHR;
    return 0;
}

int _isatty(int file) 
{ 
	return 1; 
}

int _getpid(void) 
{
    return 1;
}

int _kill(int pid, int sig)
{
    (void)pid;
    (void)sig;
    
    errno = EINVAL;
    return -1;
}