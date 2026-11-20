#include <stdio.h>
#include <stdint.h>
#include <string.h>
int main(){ char line[4096];
 while(fgets(line,sizeof line,stdin)){ size_t n=strlen(line); while(n&&(line[n-1]=='\n'||line[n-1]=='\r')) line[--n]=0; if(!n) continue;
  uint64_t h=0xcbf29ce484222325ULL; for(size_t i=0;i<n;i++){ h^=(unsigned char)line[i]; h*=0x100000001b3ULL; }
  printf("%016llx\t%s\n",(unsigned long long)h,line);} }
