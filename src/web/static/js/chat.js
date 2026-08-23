/**
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
 */

import { api } from "./api-client.js";

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
