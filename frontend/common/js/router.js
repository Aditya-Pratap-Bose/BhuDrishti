function goTo(path){window.location.href=path}
function requireSession(loginPath='../auth/login.html'){if(typeof getAuthToken==='function'&&!getAuthToken()){goTo(loginPath);return false}return true}
function signOut(loginPath='../auth/login.html'){if(typeof clearSession==='function')clearSession();goTo(loginPath)}