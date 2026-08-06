/**
 * Tableau de bord GalSen IA.
 *
 * Chaque panneau est une petite fonction de rendu : composition sans cadriciel,
 * comme le prévoit l'ADR-008. Aucun appel `fetch` ici — tout passe par le
 * client d'API.
 *
 * Règle tenue partout dans ce fichier : **ne jamais afficher une donnée qu'on
 * n'a pas**. Un panneau qui n'a pas pu charger dit pourquoi ; il n'affiche pas
 * un tableau vide qui se lirait comme « il n'y a rien ».
 */

import { api, ErreurAPI, enregistrerCle, lireCle, oublierCle } from "./api-client.js";

/** Raccourci de sélection. */
const $ = (selecteur) => document.querySelector(selecteur);

/** Crée un élément avec du texte, sans jamais interpréter de HTML. */
function element(balise, texte = "", classe = "") {
  const noeud = document.createElement(balise);
  // textContent et non innerHTML : une donnée venue de l'API ne doit jamais
  // pouvoir devenir du balisage.
  if (texte !== "") noeud.textContent = texte;
  if (classe) noeud.className = classe;
  return noeud;
}

/** Traduit un statut en pastille colorée. */
function pastille(statut) {
  const classes = {
    ready: "etat--ok",
    healthy: "etat--ok",
    degraded: "etat--attention",
    not_configured: "etat--attention",
    unavailable: "etat--attention",
    unhealthy: "etat--probleme",
    unreachable: "etat--probleme",
    unauthorized: "etat--probleme",
    error: "etat--probleme",
  };
  return element("span", statut, `etat ${classes[statut] || "etat--attention"}`);
}

/** Affiche un message d'erreur exploitable dans un panneau. */
function afficherErreur(conteneur, erreur) {
  conteneur.replaceChildren();
  const boite = element("div", "", "message message--erreur");
  boite.appendChild(element("strong", erreur.message));
  if (erreur.detail) {
    boite.appendChild(element("div", erreur.detail, "discret"));
  }
  if (erreur instanceof ErreurAPI && erreur.estProblemeDeCle) {
    boite.appendChild(
      element("div", "Renseignez une clé API valide en haut de page.", "discret"),
    );
  }
  conteneur.appendChild(boite);
}

/** Construit un tableau à partir d'en-têtes et de lignes déjà rendues. */
function tableau(entetes, lignes) {
  const table = element("table");
  const thead = element("thead");
  const ligneEntete = element("tr");
  entetes.forEach((titre) => ligneEntete.appendChild(element("th", titre)));
  thead.appendChild(ligneEntete);
  table.appendChild(thead);

  const corps = element("tbody");
  lignes.forEach((ligne) => corps.appendChild(ligne));
  table.appendChild(corps);
  return table;
}

/** Panneau : santé de la plateforme. */
async function rendreSante() {
  const conteneur = $("#sante");
  try {
    const rapport = await api.sante();
    conteneur.replaceChildren();

    const resume = element("p");
    resume.appendChild(element("span", "État global : "));
    resume.appendChild(pastille(rapport.status));
    conteneur.appendChild(resume);

    const lignes = Object.entries(rapport.components || {}).map(([nom, detail]) => {
      const ligne = element("tr");
      ligne.appendChild(element("td", nom));
      const cellule = element("td");
      cellule.appendChild(pastille(detail.status));
      ligne.appendChild(cellule);
      ligne.appendChild(element("td", detail.message || detail.error || "—", "discret"));
      return ligne;
    });
    conteneur.appendChild(tableau(["Composant", "État", "Détail"], lignes));
  } catch (erreur) {
    afficherErreur(conteneur, erreur);
  }
}

/** Panneau : connecteurs externes. */
async function rendreConnecteurs(verifier = false) {
  const conteneur = $("#connecteurs");
  try {
    const donnees = verifier
      ? await api.connecteurs.verifier()
      : await api.connecteurs.lister();
    conteneur.replaceChildren();

    const entrees = verifier ? donnees.connectors : donnees.connectors;
    if (!entrees.length) {
      conteneur.appendChild(element("p", "Aucun connecteur enregistré.", "discret"));
      return;
    }

    const lignes = entrees.map((entree) => {
      const ligne = element("tr");
      ligne.appendChild(element("td", entree.connector_id));
      ligne.appendChild(element("td", entree.kind));
      const cellule = element("td");
      if (verifier) {
        cellule.appendChild(pastille(entree.status));
      } else {
        cellule.appendChild(element("span", "non vérifié", "discret"));
      }
      ligne.appendChild(cellule);
      ligne.appendChild(
        element("td", entree.detail || entree.summary || "—", "discret"),
      );
      return ligne;
    });

    conteneur.appendChild(tableau(["Connecteur", "Type", "État", "Détail"], lignes));
    if (!verifier) {
      conteneur.appendChild(
        element(
          "p",
          "L'inventaire ne contacte aucun service. Utilisez « Vérifier » pour les interroger.",
          "discret",
        ),
      );
    }
  } catch (erreur) {
    afficherErreur(conteneur, erreur);
  }
}

/** Panneau : clés API, avec révocation. */
async function rendreCles() {
  const conteneur = $("#cles");
  try {
    const donnees = await api.cles.lister();
    conteneur.replaceChildren();

    const lignes = donnees.keys.map((cle) => {
      const ligne = element("tr");
      ligne.appendChild(element("td", cle.fingerprint));
      ligne.appendChild(element("td", cle.role));

      const etat = element("td");
      etat.appendChild(pastille(cle.revoked ? "unauthorized" : "ready"));
      ligne.appendChild(etat);

      const action = element("td");
      const bouton = element(
        "button",
        cle.revoked ? "Restaurer" : "Révoquer",
        "secondaire",
      );
      bouton.addEventListener("click", async () => {
        bouton.disabled = true;
        try {
          if (cle.revoked) {
            await api.cles.restaurer(cle.fingerprint);
          } else {
            await api.cles.revoquer(cle.fingerprint);
          }
          await rendreCles();
        } catch (erreur) {
          afficherErreur(conteneur, erreur);
        }
      });
      action.appendChild(bouton);
      ligne.appendChild(action);
      return ligne;
    });

    conteneur.appendChild(tableau(["Empreinte", "Rôle", "État", ""], lignes));
    conteneur.appendChild(
      element(
        "p",
        "Une révocation prend effet immédiatement mais ne survit pas au redémarrage : "
          + "retirez aussi la clé de GALSEN_API_KEYS.",
        "discret",
      ),
    );
  } catch (erreur) {
    afficherErreur(conteneur, erreur);
  }
}

/** Recharge tous les panneaux. */
async function toutCharger() {
  await Promise.all([rendreSante(), rendreConnecteurs(false), rendreCles()]);
}

/** Met en place la barre de saisie de la clé API. */
function preparerBarreDeCle() {
  const champ = $("#cle-api");
  champ.value = lireCle();

  $("#enregistrer-cle").addEventListener("click", async () => {
    const valeur = champ.value.trim();
    if (valeur) {
      enregistrerCle(valeur);
    } else {
      oublierCle();
    }
    await toutCharger();
  });

  $("#verifier-connecteurs").addEventListener("click", () => rendreConnecteurs(true));
  $("#recharger").addEventListener("click", toutCharger);
}

document.addEventListener("DOMContentLoaded", () => {
  preparerBarreDeCle();
  toutCharger();
});
