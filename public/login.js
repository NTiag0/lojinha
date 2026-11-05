const form=document.querySelector('#loginform');
form.addEventListener('submit',async event=>{
    event.preventDefault();const button=form.querySelector('button');button.disabled=true;
    document.querySelector('#loginerror').textContent='';
    try{
        const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:form.elements.username.value.trim(),password:form.elements.password.value})});
        const result=await response.json();
        if(!response.ok)throw Error(result.error||'Não foi possível entrar.');
        form.elements.password.value='';location.replace('/');
    }catch(error){document.querySelector('#loginerror').textContent=error.message;}
    finally{button.disabled=false;}
});
