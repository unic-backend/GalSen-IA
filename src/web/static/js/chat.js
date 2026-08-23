/**
 * Conversation GalSen IA — ch. 04 du VOLET chat-first.
 *
 * Cet script gère tout ce qui arrive après un clic « Envoyer » :
 * l'affichage, l'historique, l'état d'attente, les erreurs.
 *
 * Il réutilise `api-client.js`, jamais un second client. Deux clients
 * ferraient diverger sur la gestion de la clé, et deux implémentations de la
 * même logique se contredisent invariablement.
 */

import { api } from "./api-client.js";

// --- État global ---

/** La conversation en mémoire, avec ses tours et son ID. */
let etatConversation = {
  id: `conv_${Math.random().toString(36).slice(2, 14)}`,
  tours: [],
};

/** Le domaine imposé par l'utilisateur, ou null si automatique. */
let domaineImposeParUtilisateur = null;

// --- Point d'entrée ---

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialiser);
} else {
  initialiser();
}

function initialiser() {
  const formulaire = document.getElementById("composeur");
  const textarea = document.getElementById("message");
  const boutonEnvoyer = document.getElementById("envoyer");
  const accueil = document.getElementById("accueil");
  const pistes = document.querySelectorAll(".piste");

  if (!formulaire || !textarea) return;

  // Une piste = l'utilisateur clique et elle remplit le champ.
  pistes.forEach((bouton) => {
    bouton.addEventListener("click", () => {
      textarea.value = bouton.textContent.trim();
      textarea.focus();
    });
  });

  // Entrée = envoi. Shift+Entrée = nouvelle ligne.
  textarea.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" && !evt.shiftKey) {
      evt.preventDefault();
      formulaire.dispatchEvent(new Event("submit"));
    }
  });

  // Envoyer un message.
  formulaire.addEventListener("submit", (evt) => {
    evt.preventDefault();
    const message = textarea.value.trim();

    if (!message) return;

    // Masquer l'accueil au premier message.
    if (accueil) accueil.style.display = "none";

    textarea.value = "";
    boutonEnvoyer.disabled = true;
    ajusterHauteurTextarea(textarea);

    afficherTourUtilisateur(message);
    afficherIndicateurAttente();

    aller(message, domaineImposeParUtilisateur);
  });

  // Ajuster la hauteur du textarea à la saisie.
  textarea.addEventListener("input", () => ajusterHauteurTextarea(textarea));
}

/**
 * Envoyer le message via `/chat` et afficher la réponse.
 */
async function aller(message, domaine) {
  const textarea = document.getElementById("message");
  const boutonEnvoyer = document.getElementById("envoyer");
  const etat = document.getElementById("etat");

  try {
    const reponse = await api.post("/chat", {
      message,
      history: etatConversation.tours,
      conversation_id: etatConversation.id,
      domain: domaine || undefined,
    });

    // Garder le message et la réponse dans l'historique.
    etatConversation.tours.push({ role: "user", content: message });
    etatConversation.tours.push({
      role: "assistant",
      content: reponse.answer || "",
    });

    // Afficher la réponse avec ses marges d'ancrage.
    afficherReponse(reponse);

    if (etat) {
      etat.textContent = "";
      etat.classList.remove("echec");
    }
  } catch (erreur) {
    afficherErreur(erreur);
    if (etat) {
      etat.textContent = `Erreur : ${erreur.message || "impossible de répondre"}`;
      etat.classList.add("echec");
    }
  } finally {
    boutonEnvoyer.disabled = false;
    if (textarea) textarea.focus();
  }
}

/**
 * Affiche le message de l'utilisateur dans la conversation.
 */
function afficherTourUtilisateur(message) {
  const conversation = document.getElementById("conversation");
  if (!conversation) return;

  const tour = document.createElement("div");
  tour.className = "tour de-moi";

  const bulle = document.createElement("div");
  bulle.className = "bulle";
  bulle.textContent = message;

  tour.appendChild(bulle);
  conversation.appendChild(tour);
  conversation.scrollTop = conversation.scrollHeight;
}

/**
 * Affiche un indicateur d'attente : « ... » qui respire.
 */
function afficherIndicateurAttente() {
  const conversation = document.getElementById("conversation");
  if (!conversation) return;

  const tour = document.createElement("div");
  tour.className = "tour de-galsen";
  tour.id = "tour-attente";

  const bulle = document.createElement("div");
  bulle.className = "bulle";
  const attente = document.createElement("span");
  attente.className = "attente";
  attente.innerHTML = "<span></span><span></span><span></span>";
  bulle.appendChild(attente);

  tour.appendChild(bulle);
  conversation.appendChild(tour);
  conversation.scrollTop = conversation.scrollHeight;
}

/**
 * Remplace l'indicateur d'attente par la vraie réponse.
 */
function afficherReponse(charge) {
  const conversation = document.getElementById("conversation");
  const tourAttente = document.getElementById("tour-attente");

  if (!conversation) return;

  // Supprimer l'indicateur d'attente s'il existe.
  if (tourAttente) tourAttente.remove();

  const tour = document.createElement("div");
  tour.className = "tour de-galsen";

  const bulle = document.createElement("div");
  bulle.className = "bulle";
  bulle.textContent = charge.answer || "";

  // Les marges (ancrage, domaine, durée).
  const marges = document.createElement("div");
  marges.className = "marges";

  if (charge.grounding) {
    const jeton = document.createElement("span");
    jeton.className = `jeton ancrage jeton.${charge.grounding.status.toLowerCase()}`;
    jeton.textContent = charge.grounding.status;
    marges.appendChild(jeton);
  }

  if (charge.detection && charge.detection.domain.length > 0) {
    const jeton = document.createElement("span");
    jeton.className = "jeton domaine";
    jeton.textContent = charge.detection.domain.join(", ");
    marges.appendChild(jeton);

    if (charge.detection.method && !charge.detection.forced_by_user) {
      const motif = document.createElement("p");
      motif.className = "motif";
      motif.textContent = `par ${charge.detection.method}`;
      marges.appendChild(motif);
    }
  }

  if (charge.elapsed_seconds) {
    const jeton = document.createElement("span");
    jeton.className = "jeton";
    jeton.style.color = "var(--texte-doux)";
    jeton.textContent = `${charge.elapsed_seconds.toFixed(2)}s`;
    marges.appendChild(jeton);
  }

  bulle.appendChild(marges);
  tour.appendChild(bulle);
  conversation.appendChild(tour);
  conversation.scrollTop = conversation.scrollHeight;
}

/**
 * Affiche une erreur sous le composeur.
 */
function afficherErreur(erreur) {
  const conversation = document.getElementById("conversation");
  if (!conversation) return;

  const tourAttente = document.getElementById("tour-attente");
  if (tourAttente) tourAttente.remove();

  // L'erreur s'affiche dans la ligne d'état, déjà gérée dans `aller()`.
  // On n'ajoute pas un tour complet d'erreur dans la conversation : ce serait
  // du bruit. La ligne d'état suffit.
}

/**
 * Ajuste la hauteur du textarea à son contenu.
 */
function ajusterHauteurTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 320) + "px";
}
