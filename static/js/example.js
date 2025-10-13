function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

document.getElementById("call-api").addEventListener("click", () => {
  const endpoint = document.getElementById("endpoint").value || "/users/api/users/me/";
  const token = document.getElementById("token").value || "";

  fetch(endpoint, {
    method: "GET",
    headers: {
      "Accept": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": getCookie('csrftoken'),
      ...(token ? {"Authorization": token} : {})
    },
    credentials: 'same-origin'
  })
    .then(async (res) => {
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch(e) { data = text; }

      if (res.ok && data && data.ok !== false) {
        const display = (data.ok === true && data.data) ? data.data : data;
        document.getElementById("result-pre").innerText = JSON.stringify(display, null, 2);
        document.getElementById("result-area").style.display = "block";
        document.getElementById("error-area").style.display = "none";
      } else {
        const msg = (data && data.error && data.error.message) ? data.error.message
                  : (data && data.message) ? data.message
                  : JSON.stringify(data);
        document.getElementById("error-text").innerText = msg || "알 수 없는 에러";
        document.getElementById("error-area").style.display = "block";
        document.getElementById("result-area").style.display = "none";
      }
    })
    .catch((err) => {
      document.getElementById("error-text").innerText = "네트워크 오류";
      document.getElementById("error-area").style.display = "block";
      document.getElementById("result-area").style.display = "none";
      console.error(err);
    });
});
