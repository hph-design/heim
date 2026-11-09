import sys,re
p=sys.argv[1]; s=open(p,encoding="utf-8").read()
if 'id="gate"' in s: print("gate already present"); sys.exit(0)
H="heimfo-v1:600000:ltBnXUfia2BWY1/7tOPvXQ==:IyNrsLC+MqPcBm1sUF3ToWF85+N0Z0YqHxaLfEu222g="
s=s.replace('<meta name="referrer" content="no-referrer">','<meta name="referrer" content="no-referrer">\n<meta name="robots" content="noindex,nofollow">',1)
css='''
html.locked body>*:not(#gate){display:none!important}
#gate{display:none}
html.locked #gate{display:grid;place-items:center;min-height:100vh;padding:24px 16px;background:linear-gradient(160deg,#FBE3CF 0%,#FBF8F5 70%)}
.gatebox{width:100%;max-width:380px;background:#fff;border:1px solid var(--line);border-top:5px solid var(--green);border-radius:var(--r);box-shadow:0 8px 24px rgba(163,71,12,.12);padding:28px 24px;display:flex;flex-direction:column;gap:14px}
.gatebox .logo{color:var(--ink)}
.gatebox p{margin:0;color:var(--muted);font-size:15px}
.gatebox input{font:inherit;font-size:16px;padding:11px 12px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);width:100%}
.gatebox .err{color:var(--red);font-size:14px;font-weight:600;min-height:1.2em}
</style>
<script>try{if(sessionStorage.getItem("heimfo_ok")!=="1")document.documentElement.classList.add("locked")}catch(e){document.documentElement.classList.add("locked")}</script>
</head>'''
i=s.index('</style>\n</head>'); s=s[:i]+css+s[i+len('</style>\n</head>'):]
gate='''<body>
<div id="gate"><form class="gatebox" id="gateform">
  <span class="logo"><svg width="34" height="30" viewBox="0 0 34 30" aria-hidden="true"><path d="M2 15 17 3l15 12" fill="none" stroke="#D9661F" stroke-width="4.5" stroke-linejoin="round" stroke-linecap="round"/><path d="M8 17v11h18V17" fill="none" stroke="#161717" stroke-width="3.5" stroke-linejoin="round"/><rect x="14.5" y="20" width="5" height="8" fill="#D92128"/></svg><span>Heim<b>.fo</b></span></span>
  <p>Royndarútgáva. Skriva loyniorðið fyri at síggja síðuna.</p>
  <input type="password" id="gatepw" autocomplete="current-password" aria-label="Loyniorð" placeholder="Loyniorð" required autofocus>
  <button class="btn" type="submit" id="gatebtn">Lat upp</button>
  <div class="err" id="gateerr" role="alert"></div>
</form></div>'''
s=s.replace('<body>',gate,1)
js='''addEventListener("hashchange",route);
const PW_HASH="'''+H+'''";
async function checkPw(pw){const [,it,salt,hash]=PW_HASH.split(":");const b64=x=>Uint8Array.from(atob(x),c=>c.charCodeAt(0));const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(pw),"PBKDF2",false,["deriveBits"]);const bits=new Uint8Array(await crypto.subtle.deriveBits({name:"PBKDF2",hash:"SHA-256",salt:b64(salt),iterations:+it},key,256));return btoa(String.fromCharCode(...bits))===hash}
if(document.documentElement.classList.contains("locked")){gateform.addEventListener("submit",async e=>{e.preventDefault();gatebtn.disabled=true;gateerr.textContent="";let ok=false;try{ok=await checkPw(gatepw.value)}catch(err){}gatebtn.disabled=false;if(!ok){gateerr.textContent="Skeivt loyniorð.";gatepw.select();return}try{sessionStorage.setItem("heimfo_ok","1")}catch(err){}document.documentElement.classList.remove("locked");route()})}else route();
'''
n=s.count('addEventListener("hashchange",route);\nroute();')
if n!=1: sys.exit("ERROR: could not find route() call; gate NOT added")
s=s.replace('addEventListener("hashchange",route);\nroute();',js,1)
for k in ['id="gate"','PW_HASH','robots']: assert k in s
open(p,"w",encoding="utf-8").write(s); print("gate added")
