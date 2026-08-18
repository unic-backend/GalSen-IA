/**
 * Media Studio — les cinq zones de la directive §34, sur l'état réel du moteur.
 *
 * La tentation d'un studio est le décor : un cadre noir avec un bouton de
 * lecture, une timeline garnie de blocs colorés, une jauge de rendu qui monte.
 * Tout cela se dessine en une heure et ne demande aucun moteur — ce qui est
 * précisément le problème. Un utilisateur regarde ces éléments et en conclut
 * que la plateforme fait ce qu'ils montrent.
 *
 * Ici chaque zone affiche ce que le serveur a **mesuré** :
 *
 * - l'aperçu dit quelle capacité manque au lieu d'exposer un lecteur vide ;
 * - la timeline reste explicitement sans piste tant qu'aucun média n'a été
 *   mesuré, parce que des blocs décoratifs se lisent comme des plans ;
 * - l'avancement d'un rendu affiche « inconnu » quand le total l'est — jamais
 *   0 %, qui se lirait comme « commencé » ;
 * - une demande incomplète affiche ses **questions**, la réponse que l'API
 *   donne, et non un plan complété d'office.
 *
 * Aucun `fetch` ici : tout passe par `api-client.js` (ADR-008). Aucun
 * `innerHTML` : une donnée d'API ne doit jamais pouvoir devenir du balisage.
 */

import { api, ErreurAPI, enregistrerCle, lireCle } from "./api-client.js";

/** Raccourci de sélection. */
const $ = (selecteur) => document.querySelector(selecteur);

/** Crée un élément avec du texte, sans jamais interpréter de HTML. */
function element(balise, texte = "", classe = "") {
  const noeud = document.createElement(balise);
  // textContent et non innerHTML : le nom d'un projet vient de l'utilisateur.
  if (texte !== "") noeud.textContent = texte;
  if (classe) noeud.className = classe;
  return noeud;
}

/** Vide un conteneur avant de le redessiner. */
function vider(conteneur) {
  while (conteneur.firstChild) conteneur.removeChild(conteneur.firstChild);
}

/** Affiche un message d'erreur exploitable, avec son détail. */
function afficherErreur(conteneur, erreur) {
  vider(conteneur);
  const message = erreur instanceof ErreurAPI ? erreur.message : "Erreur inattendue.";
  conteneur.appendChild(element("p", message, "message message--erreur"));
  const detail = erreur && erreur.detail;
  if (detail) {
    conteneur.appendChild(
      element("p", typeof detail === "string" ? detail : JSON.stringify(detail), "discret"),
    );
  }
}

/** L'état de l'application, entièrement en mémoire de page. */
const etat = {
  projet: null,
  travail: null,
  capacites: null,
};

// ----------------------------------------------------------------------
// HAUT — capacités et aptitude
// ----------------------------------------------------------------------

/**
 * Charge ce que la machine peut réellement faire et redessine les zones qui
 * en dépendent.
 */
async function chargerCapacites() {
  const panneau = $("#panneau-capacites");
  try {
    etat.capacites = await api.media.capacites();
  } catch (erreur) {
    afficherErreur(panneau, erreur);
    return;
  }

  const { capabilities, tools, readiness } = etat.capacites;
  vider(panneau);

  const liste = element("ul", "", "liste-etapes");
  Object.entries(capabilities.capabilities).forEach(([nom, detail]) => {
    const ligne = element("li");
    ligne.appendChild(element("span", nom));
    ligne.appendChild(element("span", detail.state, pastilleDe(detail.state)));
    ligne.title = detail.reason;
    liste.appendChild(ligne);
  });
  panneau.appendChild(liste);

  panneau.appendChild(
    element(
      "p",
      `${tools.runnable.length} outil(s) exécutable(s) ici sur ${tools.count}.`,
      "discret",
    ),
  );

  const aptitude = $("#etat-aptitude");
  aptitude.textContent = readiness.state;
  aptitude.className = `etat ${readiness.counts.ABSENT > 0 ? "etat--probleme" : "etat--attention"}`;
  aptitude.title =
    "État calculé sur les dix-sept étapes de la chaîne, pas écrit d'avance.";

  dessinerEtapes(readiness);
  dessinerApercu(readiness);
  dessinerTimeline(readiness);
}

/** La classe d'une pastille d'état de capacité. */
function pastilleDe(etatCapacite) {
  if (etatCapacite === "AVAILABLE") return "etat etat--ok";
  if (etatCapacite === "DEGRADED") return "etat etat--attention";
  return "etat etat--probleme";
}

// ----------------------------------------------------------------------
// GAUCHE — les étapes de la chaîne
// ----------------------------------------------------------------------

/** Liste les dix-sept étapes avec leur état mesuré. */
function dessinerEtapes(aptitude) {
  const panneau = $("#panneau-etapes");
  vider(panneau);

  const liste = element("ul", "", "liste-etapes");
  aptitude.stages.forEach((etape) => {
    const ligne = element("li");
    ligne.appendChild(element("span", etape.stage));
    const marque =
      etape.state === "READY"
        ? "etat etat--ok"
        : etape.state === "BLOCKED"
          ? "etat etat--attention"
          : "etat etat--probleme";
    ligne.appendChild(element("span", etape.state, marque));
    // Le titre porte la raison : bloqué s'installe, absent s'écrit.
    ligne.title = etape.reason;
    liste.appendChild(ligne);
  });
  panneau.appendChild(liste);
}

// ----------------------------------------------------------------------
// CENTRE — aperçu
// ----------------------------------------------------------------------

/**
 * L'aperçu dit ce qui manque plutôt que d'exposer un lecteur vide.
 *
 * Un cadre noir avec un bouton de lecture sur un fichier qui n'existe pas est
 * la façon la plus efficace de faire croire qu'une vidéo a été produite.
 */
function dessinerApercu(aptitude) {
  const panneau = $("#panneau-apercu");
  vider(panneau);

  const master = aptitude.stages.find((etape) => etape.stage === "FINAL_MASTER");
  if (master && master.state === "READY") {
    panneau.appendChild(element("p", "Prêt à rendre un master sur cette machine."));
    panneau.appendChild(
      element(
        "p",
        "L'aperçu s'affichera après un rendu réellement écrit — un encodage terminé n'est pas encore une production réussie (§21).",
        "discret",
      ),
    );
    return;
  }

  panneau.appendChild(element("p", "Aucun aperçu : le master ne peut pas être écrit ici."));
  const manquantes = (aptitude.missing_capabilities || []).join(", ");
  panneau.appendChild(
    element(
      "p",
      manquantes
        ? `Capacités absentes de cette machine : ${manquantes}.`
        : "Aucune capacité manquante rapportée.",
      "discret",
    ),
  );
  panneau.appendChild(
    element(
      "p",
      "Un lecteur vide affiché ici se lirait comme une vidéo produite.",
      "discret",
    ),
  );
}

// ----------------------------------------------------------------------
// BAS — timeline
// ----------------------------------------------------------------------

/**
 * La timeline se dessine sur des scènes mesurées, et sur rien d'autre.
 *
 * Tant que la détection de plans est bloquée, la zone dit ce qui manque : des
 * blocs décoratifs se lisent comme des plans, et personne ne peut deviner
 * qu'ils sont décoratifs.
 */
function dessinerTimeline(aptitude) {
  const panneau = $("#panneau-timeline");
  vider(panneau);

  const scenes = aptitude.stages.find((etape) => etape.stage === "SCENES");
  const montage = aptitude.stages.find((etape) => etape.stage === "EDITING");
  const bloquees = [scenes, montage].filter((etape) => etape && etape.state !== "READY");

  if (bloquees.length > 0) {
    const raison = bloquees
      .map((etape) => `${etape.stage} : ${etape.missing.map((m) => m.capability).join(", ")}`)
      .join(" · ");
    const vide = element(
      "div",
      `Aucune piste : rien n'a été mesuré. ${raison}. Des blocs dessinés ici se liraient comme des plans détectés.`,
      "piste-vide",
    );
    panneau.appendChild(vide);
    return;
  }

  panneau.appendChild(
    element("p", "Prêt à détecter des plans sur un média mesuré.", "discret"),
  );
}

// ----------------------------------------------------------------------
// GAUCHE — production
// ----------------------------------------------------------------------

/** Ouvre une production et affiche son manifeste. */
async function ouvrirProjet(evenement) {
  evenement.preventDefault();
  const panneau = $("#panneau-projet");
  const objectif = $("#objectif-projet").value.trim();

  try {
    const cree = await api.media.creerProjet(objectif);
    etat.projet = cree.project_id;
    const manifeste = await api.media.projet(cree.project_id);

    vider(panneau);
    panneau.appendChild(element("p", manifeste.objective));
    panneau.appendChild(element("p", `Identité : ${manifeste.project_id}`, "discret"));
    panneau.appendChild(
      element(
        "p",
        `${manifeste.version_count} version(s) — toutes conservées, aucune n'est remplacée en silence.`,
        "discret",
      ),
    );
    $("#lancer-rendu").disabled = false;
  } catch (erreur) {
    afficherErreur(panneau, erreur);
  }
}

// ----------------------------------------------------------------------
// CENTRE — demande en langage naturel
// ----------------------------------------------------------------------

/**
 * Construit un plan, ou affiche les questions restées ouvertes.
 *
 * `CLARIFICATION_REQUIRED` est une réponse, pas un échec : l'afficher comme
 * une erreur pousserait l'utilisateur à recommencer au lieu de répondre.
 */
async function construirePlan(evenement) {
  evenement.preventDefault();
  const panneau = $("#panneau-plan");

  if (!etat.projet) {
    vider(panneau);
    panneau.appendChild(element("p", "Ouvrez d'abord une production.", "discret"));
    return;
  }

  try {
    const plan = await api.media.plan(etat.projet, $("#demande").value);
    vider(panneau);

    if (plan.status === "CLARIFICATION_REQUIRED") {
      panneau.appendChild(
        element("p", "Il manque des éléments pour planifier. Aucun n'est choisi à votre place :"),
      );
      plan.clarifications.forEach((question) => {
        panneau.appendChild(element("p", question.question, "question"));
      });
      return;
    }

    panneau.appendChild(element("p", `Domaine : ${plan.request.domain}`));
    if (plan.request.duration_seconds !== null) {
      panneau.appendChild(
        element("p", `Durée demandée : ${plan.request.duration_seconds} s`, "discret"),
      );
    }
    dessinerChaine(panneau, plan.chain);
  } catch (erreur) {
    afficherErreur(panneau, erreur);
  }
}

/** Dessine l'enchaînement d'outils, en marquant ceux qu'une capacité bloque. */
function dessinerChaine(panneau, chaine) {
  if (!chaine) return;
  const piste = element("div", "", "piste");
  chaine.steps.forEach((etape) => {
    const bloque = (chaine.blocked || []).includes(etape.tool);
    const bloc = element("span", etape.tool, `bloc ${bloque ? "bloc--bloque" : ""}`.trim());
    bloc.title = bloque
      ? "Outil bloqué par une capacité absente, pas par l'ordre."
      : "Exécutable ici.";
    piste.appendChild(bloc);
  });
  panneau.appendChild(piste);
}

// ----------------------------------------------------------------------
// DROITE — rendu
// ----------------------------------------------------------------------

/** Dépose un rendu et affiche son état réel. */
async function lancerRendu() {
  const panneau = $("#panneau-travail");
  if (!etat.projet) return;

  try {
    const depose = await api.media.rendre(etat.projet, $("#nom-sortie").value);
    etat.travail = depose.job_id;
    $("#annuler-rendu").disabled = false;
    afficherTravail(await api.media.travail(depose.job_id));
  } catch (erreur) {
    afficherErreur(panneau, erreur);
  }
}

/** Annule le rendu en cours. L'annulation est terminale. */
async function annulerRendu() {
  const panneau = $("#panneau-travail");
  if (!etat.travail) return;

  try {
    await api.media.annuler(etat.travail, "annulé depuis le studio");
    afficherTravail(await api.media.travail(etat.travail));
    $("#annuler-rendu").disabled = true;
  } catch (erreur) {
    afficherErreur(panneau, erreur);
  }
}

/**
 * Affiche l'état d'un rendu.
 *
 * Un total inconnu affiche « inconnu » : `0 %` se lirait comme un travail
 * commencé, et un pourcentage calculé sur le temps écoulé atteint 90 % et y
 * reste.
 */
function afficherTravail(travail) {
  const panneau = $("#panneau-travail");
  vider(panneau);

  panneau.appendChild(element("p", `État : ${travail.status}`));
  panneau.appendChild(
    element(
      "p",
      travail.progress === null
        ? "Avancement : inconnu (total non compté)"
        : `Avancement : ${Math.round(travail.progress * 100)} %`,
      "discret",
    ),
  );
  panneau.appendChild(element("p", travail.progress_note, "discret"));
  if (travail.attempt_count > 0) {
    panneau.appendChild(
      element(
        "p",
        `${travail.attempt_count} tentative(s) conservée(s) : une réussite à la troisième n'est pas une réussite.`,
        "discret",
      ),
    );
  }
}

// ----------------------------------------------------------------------
// Démarrage
// ----------------------------------------------------------------------

/** Branche les commandes et charge l'état mesuré. */
function demarrer() {
  const champCle = $("#cle-api");
  const cle = lireCle();
  if (cle) champCle.value = cle;

  $("#enregistrer-cle").addEventListener("click", () => {
    enregistrerCle(champCle.value.trim());
    chargerCapacites();
  });
  $("#formulaire-projet").addEventListener("submit", ouvrirProjet);
  $("#formulaire-plan").addEventListener("submit", construirePlan);
  $("#lancer-rendu").addEventListener("click", lancerRendu);
  $("#annuler-rendu").addEventListener("click", annulerRendu);

  chargerCapacites();
}

document.addEventListener("DOMContentLoaded", demarrer);
