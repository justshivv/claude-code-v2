import re
def tokenize(s):
    i=0;n=len(s)
    while i<n:
        c=s[i]
        if c in '()': yield c; i+=1
        elif c.isspace(): i+=1
        elif c=='"':
            j=i+1; buf=[]
            while s[j]!='"':
                if s[j]=='\\': buf.append(s[j:j+2]); j+=2
                else: buf.append(s[j]); j+=1
            yield ('S',''.join(buf)); i=j+1
        else:
            j=i
            while j<n and not s[j].isspace() and s[j] not in '()': j+=1
            yield s[i:j]; i=j
def parse(s):
    stack=[[]]
    for t in tokenize(s):
        if t=='(': stack.append([])
        elif t==')': x=stack.pop(); stack[-1].append(x)
        else: stack[-1].append(t)
    return stack[0]
def dump(x, ind=0):
    if isinstance(x, tuple): return '"'+x[1]+'"'
    if isinstance(x, str): return x
    return '('+' '.join(dump(e) for e in x)+')'
