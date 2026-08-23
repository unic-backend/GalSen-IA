<<<<<<< HEAD
﻿/**
 * Interface conversationnelle GalSen IA â€” logique d'affichage (chapitre 01, phase 1.2).
 *
 * Ce fichier construit la couche de prÃ©sentation du chat : bulles utilisateur et
 * assistant, indicateur Â« en cours Â», messages d'erreur et saisie vocale. Le
 * cÃ¢blage sur l'orchestration (POST /workflow/run via api-client.js) arrive au
 * chapitre 02 ; ici, seule la structure interactive est en place.
 *
 * RÃ¨gles respectÃ©es (ADR-008) :
 * - aucune Ã©criture via `innerHTML` : tout texte est insÃ©rÃ© avec `textContent`
 *   pour ne jamais interprÃ©ter de balisage venu d'une rÃ©ponse d'API ;
 * - aucun `fetch` direct : le seul module autorisÃ© Ã  appeler le rÃ©seau est
 *   `api-client.js`.
=======
/**
 * Conversation GalSen IA — ch. 04 du VOLET chat-first.
 *
 * Cet script gère tout ce qui arrive après un clic « Envoyer » :
 * l'affichage, l'historique, l'état d'attente, les erreurs.
 *
 * Il réutilise `api-client.js`, jamais un second client. Deux clients
 * ferraient diverger sur la gestion de la clé, et deux implémentations de la
 * même logique se contredisent invariablement.
>>>>>>> f8b0c60f12a9156a80608b76d3a9bf2266613290
 */

import { api } from "./api-client.js";

<<<<<<< HEAD
const $ = (selecteur) => document.querySelector(selecteur);

document.addEventListener("DOMContentLoaded", () => {
  const boutonMenu = $("#menu-domaines");
  const menu = $("#liste-domaines");
  const conversation = $("#conversation");
  const formulaire = $("#formulaire-saisie");
  const saisie = $("#saisie");
  const boutonVocal = $("#bouton-vocal");

  // --- Menu des domaines ----------------------------------------------------

  /** Ferme le menu et rend l'Ã©tat au bouton qui l'ouvre. */
  function fermerMenu() {
    menu.hidden = true;
    boutonMenu.setAttribute("aria-expanded", "false");
  }

  /** Ouvre le menu. */
  function ouvrirMenu() {
    menu.hidden = false;
    boutonMenu.setAttribute("aria-expanded", "true");
  }

  if (boutonMenu && menu) {
    boutonMenu.addEventListener("click", () => {
      if (menu.hidden) ouvrirMenu();
      else fermerMenu();
    });

    // Fermeture au clavier (Ã‰chap) et au clic hors du menu.
    document.addEventListener("keydown", (evenement) => {
      if (evenement.key === "Escape") fermerMenu();
    });

    document.addEventListener("click", (evenement) => {
      const horsMenu = !menu.contains(evenement.target)
        && !boutonMenu.contains(evenement.target);
      if (!menu.hidden && horsMenu) fermerMenu();
    });
  }

  // --- Affichage des messages ----------------------------------------------

  /** Retire l'Ã©cran d'accueil quand la premiÃ¨re bulle apparaÃ®t. */
  function retirerAccueil() {
    const accueil = conversation.querySelector(".accueil");
    if (accueil) accueil.remove();
  }

  /** CrÃ©e une bulle et l'ajoute en bas de la conversation. */
  function ajouterMessage(role, texte) {
    retirerAccueil();
    const bulle = document.createElement("div");
    bulle.className = `message message--${role}`;
    bulle.textContent = texte;
    conversation.appendChild(bulle);
    conversation.scrollTop = conversation.scrollHeight;
  }

  /** Affiche l'indicateur Â« en cours Â» en bas de la conversation. */
  function afficherEnCours() {
    masquerEnCours();
    const indicateur = document.createElement("div");
    indicateur.id = "en-cours";
    indicateur.className = "message message--info";
    indicateur.textContent = "â€¦";
    conversation.appendChild(indicateur);
    conversation.scrollTop = conversation.scrollHeight;
  }

  /** Retire l'indicateur Â« en cours Â» s'il est prÃ©sent. */
  function masquerEnCours() {
    const indicateur = $("#en-cours");
    if (indicateur) indicateur.remove();
  }

  /** Affiche un message d'erreur, sans le faire passer pour une rÃ©ponse. */
  function afficherErreur(message) {
    masquerEnCours();
    const erreur = document.createElement("div");
    erreur.className = "message message--erreur";
    erreur.textContent = message;
    conversation.appendChild(erreur);
    conversation.scrollTop = conversation.scrollHeight;
  }

  // --- Saisie vocale -------------------------------------------------------

  const ReconnaissanceVocale = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (ReconnaissanceVocale && boutonVocal) {
    const reconnaissance = new ReconnaissanceVocale();
    let enEcoute = false;

    reconnaissance.lang = "fr-FR";
    reconnaissance.interimResults = false;
    reconnaissance.maxAlternatives = 1;

    reconnaissance.addEventListener("result", (evenement) => {
      const transcription = evenement.results[0][0].transcript;
      saisie.value = (saisie.value ? `${saisie.value} ` : "") + transcription;
    });

    reconnaissance.addEventListener("error", () => {
      enEcoute = false;
      boutonVocal.classList.remove("bouton-vocal--actif");
      afficherErreur("La saisie vocale n'a pas fonctionnÃ©. Utilisez le clavier.");
    });

    reconnaissance.addEventListener("end", () => {
      enEcoute = false;
      boutonVocal.classList.remove("bouton-vocal--actif");
    });

    boutonVocal.addEventListener("click", () => {
      if (enEcoute) {
        reconnaissance.stop();
        return;
      }
      enEcoute = true;
      boutonVocal.classList.add("bouton-vocal--actif");
      reconnaissance.start();
    });
  } else if (boutonVocal) {
    // Repli : sans Web Speech, le bouton est dÃ©sactivÃ© plutÃ´t que de promettre
    // une saisie vocale qui ne viendra pas.
    boutonVocal.disabled = true;
    boutonVocal.title = "Saisie vocale non disponible sur ce navigateur";
  }

  // --- Envoi ----------------------------------------------------------------

  if (formulaire && saisie && conversation) {
  formulaire.addEventListener("submit", async (evenement) => {
    evenement.preventDefault();

    const texte = saisie.value.trim();
    if (!texte) return;

    ajouterMessage("utilisateur", texte);
    saisie.value = "";
    afficherEnCours();

    try {
      const reponse = await api.workflow.run(texte);

      masquerEnCours();

      let resultat = reponse?.aggregated_result;

      if (Array.isArray(resultat)) {
        resultat = resultat
          .map((element) => {
            if (typeof element === "string") {
              return element;
            }

            if (element && typeof element.text === "string") {
              return element.text;
            }

            if (element && typeof element.result === "string") {
              return element.result;
            }

            return JSON.stringify(element);
          })
          .filter(Boolean)
          .join("\n\n");
      }

      if (
        resultat === null ||
        resultat === undefined ||
        resultat === ""
      ) {
        resultat =
          reponse?.error ||
          "Aucune réponse exploitable n'a été produite.";
      }

      if (typeof resultat !== "string") {
        resultat = JSON.stringify(resultat, null, 2);
      }

      ajouterMessage("assistant", resultat);
    } catch (erreur) {
      afficherErreur(
        erreur?.message ||
        "Impossible de contacter l'orchestrateur."
      );
    }
      });
  }
});
=======
// --- État global ---

/** La conversation en mémoire, avec ses tours et son ID. */
let etatConversation = {
  id: `conv_${Math.random().toString(36).slice(2, 14)}`,
  tours: [],
};

/** Le domaine imposé par l'utilisateur, ou null si automatique. */
let domaineImposeParUtilisateur = null;

/**
 * Les trois issues d'ancrage, avec leur classe CSS et leur libellé.
 *
 * **Cette table existe parce que son absence a déjà cassé la page.** La
 * première version fabriquait la classe par `` `jeton.${statut.toLowerCase()}` ``,
 * ce qui produisait le jeton `jeton.grounded` — un nom de classe contenant un
 * point, qui ne correspond à aucune règle. Le jeton le plus important de la
 * page s'affichait donc sans sa couleur, et personne ne le voyait puisque
 * `GROUNDED` reste rare tant que le corpus est vide.
 *
 * Un lien explicite entre le statut du serveur et la classe se casse
 * bruyamment : un statut inconnu n'a pas d'entrée, et le test le dit.
 */
const ANCRAGE = {
  GROUNDED: { classe: "ancre", libelle: "Fondé sur des sources" },
  UNGROUNDED: { classe: "sans-ancre", libelle: "Rien ne fonde cette réponse" },
  NOT_CHECKED: { classe: "non-verifie", libelle: "Non vérifié" },
};

/**
 * Retourne la classe CSS d'un statut d'ancrage.
 *
 * Un statut que le serveur ajouterait sans que cette page le sache tombe sur
 * `non-verifie` — l'issue la plus prudente des trois. Se taire vaut mieux que
 * peindre en vert quelque chose qu'on n'a pas compris.
 */
function classeAncrage(statut) {
  return (ANCRAGE[statut] || ANCRAGE.NOT_CHECKED).classe;
}

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

  // Menu des domaines
  const boutonMenu = document.getElementById("bouton-menu");
  const menu = document.getElementById("menu-domaines");
  const boutonFermer = document.getElementById("menu-fermer");
  const boutonReinitialiser = document.querySelector(".menu-reinitialiser");
  const boutonsDomine = document.querySelectorAll(".menu-domaine");

  if (boutonMenu && menu) {
    boutonMenu.addEventListener("click", () => {
      const estOuvert = !menu.hasAttribute("hidden");
      if (estOuvert) {
        menu.setAttribute("hidden", "");
        boutonMenu.setAttribute("aria-expanded", "false");
      } else {
        menu.removeAttribute("hidden");
        boutonMenu.setAttribute("aria-expanded", "true");
      }
    });
  }

  if (boutonFermer && menu) {
    boutonFermer.addEventListener("click", () => {
      menu.setAttribute("hidden", "");
      boutonMenu.setAttribute("aria-expanded", "false");
    });
  }

  boutonsDomine.forEach((bouton) => {
    bouton.addEventListener("click", () => {
      const domaine = bouton.dataset.domaine;
      domaineImposeParUtilisateur = domaine;

      // Mettre le domaine en évidence
      boutonsDomine.forEach((b) => b.classList.remove("actif"));
      bouton.classList.add("actif");

      // Fermer le menu
      menu.setAttribute("hidden", "");
      boutonMenu.setAttribute("aria-expanded", "false");

      // Optionnel : autofocus sur le textarea
      textarea.focus();
    });
  });

  if (boutonReinitialiser) {
    boutonReinitialiser.addEventListener("click", () => {
      domaineImposeParUtilisateur = null;
      boutonsDomine.forEach((b) => b.classList.remove("actif"));
      menu.setAttribute("hidden", "");
      boutonMenu.setAttribute("aria-expanded", "false");
      textarea.focus();
    });
  }
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
    retirerAttente();
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
    jeton.className = `jeton ${classeAncrage(charge.grounding.status)}`;
    jeton.textContent = ANCRAGE[charge.grounding.status]
      ? ANCRAGE[charge.grounding.status].libelle
      : charge.grounding.status;
    marges.appendChild(jeton);
  }

  if (charge.detection && charge.detection.domain.length > 0) {
    const jeton = document.createElement("span");
    jeton.className = "jeton domaine";
    // Le domaine ne s'affiche jamais seul : « agriculture » et « agriculture,
    // par mots-clés » ne se valent pas. Sans la méthode, une heuristique
    // s'affiche comme une certitude.
    jeton.textContent = charge.detection.forced_by_user
      ? `${charge.detection.domain.join(", ")} · imposé`
      : `${charge.detection.domain.join(", ")}${
          charge.detection.method ? ` · par ${charge.detection.method}` : ""
        }`;
    marges.appendChild(jeton);
  }

  if (charge.elapsed_seconds) {
    const jeton = document.createElement("span");
    jeton.className = "jeton duree";
    jeton.textContent = `${charge.elapsed_seconds.toFixed(2)} s`;
    marges.appendChild(jeton);
  }

  bulle.appendChild(marges);

  // La raison, sous les jetons et non dedans. C'est le texte que l'agent a
  // écrit lui-même pour dire ce qui manque — le jeter en gardant son seul
  // statut reviendrait à afficher « UNGROUNDED » sans dire pourquoi, ce qui
  // n'aide personne à corriger quoi que ce soit.
  if (charge.grounding && charge.grounding.reason) {
    const motif = document.createElement("p");
    motif.className = "motif";
    motif.textContent = charge.grounding.reason;
    bulle.appendChild(motif);
  }
  tour.appendChild(bulle);
  conversation.appendChild(tour);
  conversation.scrollTop = conversation.scrollHeight;
}

/**
 * Retire l'indicateur d'attente quand le tour a échoué.
 *
 * Aucune bulle d'erreur n'est ajoutée à la conversation : le message d'échec
 * vit dans la ligne d'état, sous le composeur. Une panne de réseau n'est pas
 * une chose que la plateforme a *dite*, et la placer dans le fil la ferait
 * relire comme une réponse.
 */
function retirerAttente() {
  const tourAttente = document.getElementById("tour-attente");
  if (tourAttente) tourAttente.remove();
}

/**
 * Ajuste la hauteur du textarea à son contenu.
 */
function ajusterHauteurTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 320) + "px";
}
>>>>>>> f8b0c60f12a9156a80608b76d3a9bf2266613290
