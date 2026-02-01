# Sanity Tests

## Test Tools

```
Title: Test Tools

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code. 
Find do sanity testing and find issues. 

Test out the following packs:
Packs: brave, code, context7, convert, db, diagram, excel, file, firecrawl, github, ground, llm, package, ripgrep, scaffold, web, wiki                                                                                                

When testing
- code with db at demo/.chunkhound
- convert with files at demo/data
- db with db at demo/db/northwind.db
- excel with files at demo/data

```

```
Title: Snippets

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code. 
Find issues with these tools or the underlying MCP server. 
Find do sanity testing and find issues. 

Test the existing snippets.

```

```
Title: Features

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code. 
Find issues with these tools or the underlying MCP server. 
Find do sanity testing and find issues. 

Introspection & Discovery                                                                                                                                                                                                            
- ot.help() - general help overview                                                                                
- ot.help(query="...") - exact lookup (tool, pack, snippet, alias)                                                 
- ot.help(query="...", info="list|min|full") - info levels                                                         
- ot.tools() - list all tools                                                                                      
- ot.tools(pattern="...") - filter by pattern/prefix                                                               
- ot.packs() - list all packs                                                                                      
- ot.packs(pattern="...") - filter by pattern                                                                      
- ot.aliases() - list configured aliases                                                                           
- ot.snippets() - list configured snippets                                                                         
- ot.config() - show config (aliases, snippets, servers)                                                           
- ot.health() - system health check                                                                                

Parameter Prefixes                                                                                                 
- Short prefixes work: ot.tools(p="brave", i="full") equivalent to ot.tools(pattern="brave", info="full")          

Trigger Prefixes (invocation styles)                                                                               
- __ot - short form                                                                                                
- __onetool__run - full explicit call                                                                              
- __onetool - full name, default tool                                                                              
- mcp__onetool__run - explicit MCP call                                                                            

Invocation Styles                                                                                                  
- Simple call: __ot func(arg=val)                                                                                  
- Inline backticks: __ot \func(arg=val)``                                                                          
- Code fence: multi-line Python blocks                                                                             

Alias Resolution                                                                                                   
- Alias calls resolve to target: ws(...) → brave.web_search(...)                                                   

Snippet Expansion                                                                                                  
- $snippet_name param=value expands server-side                                                                    

Output Format Control                                                                                              
- __format__ = "yml_h"; ... controls serialization                                                                 

Output Sanitization                                                                                                
- __sanitize__ = True|False controls external content sanitization                                                 

Code Execution                                                                                                     
- Multi-line code blocks with variables                                                                            
- Loops and list comprehensions                                                                                    
- Chained operations                                                                                               
- Last expression returned as result                                                                               

Security - AST Validation                                                                                          
- Blocked patterns rejected: exec(), eval(), subprocess.*                                                          
- Warned patterns logged: open(), pickle.*                                                                         

Statistics                                                                                                         
- ot.stats() - runtime statistics                                                                                  
- ot.stats(period="day|week") - filtered by period                                                                 

Configuration                                                                                                      
- ot.reload() - force config reload

```

## Tear-Down

```
Title: Tear-Down

Provide a summary of the issues found, grouped by component.
```
