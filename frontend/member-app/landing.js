const primaryCta = document.querySelector("#memberPrimaryCta");
const signIn = document.querySelector("#landingSignin");

if (VinyrdClient.token()) {
  if (primaryCta) {
    primaryCta.textContent = "Open my Vinyrd";
    primaryCta.href = "./home.html";
  }
  if (signIn) {
    signIn.textContent = "Open member home";
    signIn.href = "./home.html";
  }
}
