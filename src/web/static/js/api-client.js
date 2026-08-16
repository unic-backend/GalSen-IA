/**
 * Client d'API GalSen IA.
 *
 * Seul module à connaître l'existence des routes. Aucune page n'appelle `fetch`
 * directement : c'est ainsi que la directive du chapitre 02 — « le frontend doit
 * rester indépendant des détails d'implémentation du backend » — est tenue
 * concrètement, et non par intention.
 *
 * Il ne dépend que de `fetch`, ce qui lui permettra de survivre intact à un
 * changement de pile d'interface (ADR-008).
 */

/** Clé API du navigateur, conservée hors du code source. */
const CLE_STOCKAGE = "galsen.apiKey";

/**
 * Erreur portée par un appel qui n'a pas abouti.
 *
 * Elle distingue ce que l'utilisateur peut corriger (clé absente, droit
 * manquant) de ce qu'il ne peut pas (serveur muet), parce que les deux appellent
 * des gestes différents.
 */
export class ErreurAPI extends Error {
  constructor(message, { statut = 0, detail = "" } = {}) {
    super(message);
    this.name = "ErreurAPI";
    this.statut = statut;
    this.detail = detail;
  }

  /** Indique si l'appelant doit fournir ou corriger sa clé. */
  get estProblemeDeCle() {
    return this.statut === 401 || this.statut === 403;
  }
}

/** Retourne la clé API enregistrée dans ce navigateur, ou une chaîne vide. */
export function lireCle() {
  try {
    return window.localStorage.getItem(CLE_STOCKAGE) || "";
  } catch {
    // Navigation privée ou stockage refusé : l'interface reste utilisable,
    // simplement sans mémoriser la clé d'une visite à l'autre.
    return "";
  }
}

/** Enregistre la clé API pour les prochaines visites. */
export function enregistrerCle(cle) {
  try {
    window.localStorage.setItem(CLE_STOCKAGE, cle);
  } catch {
    /* stockage indisponible : la clé vaut pour la session en cours */
  }
}

/** Oublie la clé enregistrée. */
export function oublierCle() {
  try {
    window.localStorage.removeItem(CLE_STOCKAGE);
  } catch {
    /* rien à oublier */
  }
}

/**
 * Exécute un appel vers l'API.
 *
 * @param {string} chemin Chemin de la route, commençant par `/`.
 * @param {object} options `methode` et `corps`.
 * @returns {Promise<any>} La réponse décodée.
 * @throws {ErreurAPI} Toujours une ErreurAPI : jamais une exception brute de
 *   `fetch`, pour que l'appelant n'ait qu'une forme d'erreur à traiter.
 */
async function appeler(chemin, { methode = "GET", corps = null } = {}) {
  const entetes = { "Content-Type": "application/json" };
  const cle = lireCle();
  if (cle) {
    entetes["X-API-Key"] = cle;
  }

  let reponse;
  try {
    reponse = await fetch(chemin, {
      method: methode,
      headers: entetes,
      body: corps === null ? undefined : JSON.stringify(corps),
    });
  } catch (erreur) {
    throw new ErreurAPI("Le serveur ne répond pas.", { detail: String(erreur) });
  }

  let charge = null;
  const type = reponse.headers.get("content-type") || "";
  if (type.includes("application/json")) {
    charge = await reponse.json().catch(() => null);
  }

  if (!reponse.ok) {
    const detail = charge && charge.detail ? charge.detail : reponse.statusText;
    throw new ErreurAPI(messagePourStatut(reponse.status), {
      statut: reponse.status,
      detail,
    });
  }

  return charge;
}

/** Traduit un code HTTP en phrase utile à celui qui la lit. */
function messagePourStatut(statut) {
  switch (statut) {
    case 401:
      return "Clé API absente ou invalide.";
    case 403:
      return "Cette clé n'a pas le droit d'effectuer cette action.";
    case 404:
      return "Ressource introuvable.";
    case 429:
      return "Trop de requêtes : patientez avant de réessayer.";
    case 503:
      return "Service indisponible pour le moment.";
    default:
      return statut >= 500 ? "Erreur du serveur." : "Requête refusée.";
  }
}

/**
 * Les routes de la plateforme, regroupées par domaine.
 *
 * Ajouter une route ici est le seul endroit à modifier quand l'API évolue.
 */
export const api = {
  /** État de santé de la plateforme. Ne demande aucune clé. */
  sante: () => appeler("/health"),

  connecteurs: {
    /** Inventaire, sans aucun appel sortant côté serveur. */
    lister: () => appeler("/connectors"),
    /** Vérification réelle : contacte les services externes. */
    verifier: () => appeler("/connectors/status"),
    verifierUn: (identifiant) => appeler(`/connectors/${identifiant}/check`),
  },

  cles: {
    lister: () => appeler("/auth/keys"),
    revoquer: (empreinte) =>
      appeler(`/auth/keys/${empreinte}/revoke`, { methode: "POST" }),
    restaurer: (empreinte) =>
      appeler(`/auth/keys/${empreinte}/restore`, { methode: "POST" }),
    recharger: () => appeler("/auth/keys/reload", { methode: "POST" }),
  },

  agri: {
    /**
     * Demande un conseil agricole.
     *
     * @param {string} question Question en français ou en wolof.
     * @param {string} langue `fr` ou `wo`.
     * @param {string|null} modele Modèle imposé, ou null pour laisser choisir.
     */
    conseil: (question, langue = "fr", modele = null) =>
      appeler("/agri/advice", {
        methode: "POST",
        corps: modele
          ? { question, language: langue, model_id: modele }
          : { question, language: langue },
      }),
  },

  memoire: {
    enregistrer: (contenu, type = "short_term") =>
      appeler("/memory/store", {
        methode: "POST",
        corps: { content: contenu, memory_type: type },
      }),
  },

  notifications: {
    statistiques: () => appeler("/notification/stats"),
  },

  /**
   * Le moteur média (§29).
   *
   * Aucune de ces fonctions n'invente d'état : `capacites()` rend ce que la
   * machine peut faire, mesuré, et le studio affiche ce refus tel quel plutôt
   * que de dessiner une timeline sur un média qu'il n'a pas.
   */
  media: {
    /** Capacités mesurées, outils exécutables, frontière et aptitude. */
    capacites: () => appeler("/media/capabilities"),

    /** Ouvre une production versionnée. */
    creerProjet: (objectif) =>
      appeler("/media/projects", {
        methode: "POST",
        corps: { objective: objectif },
      }),

    /** Le manifeste complet : toutes les versions, pas seulement la courante. */
    projet: (identifiant) => appeler(`/media/projects/${identifiant}`),

    /**
     * Transforme une demande en langage naturel en plan structuré.
     *
     * Rend `CLARIFICATION_REQUIRED` avec ses questions quand la demande ne dit
     * pas tout : c'est une réponse, pas un échec.
     */
    plan: (identifiant, demande) =>
      appeler(`/media/projects/${identifiant}/plan`, {
        methode: "POST",
        corps: { request: demande },
      }),

    /** Dépose un rendu dans la file. Répond 202 : accepté, pas produit. */
    rendre: (identifiant, nom, unites = null) =>
      appeler(`/media/projects/${identifiant}/render`, {
        methode: "POST",
        corps:
          unites === null
            ? { output_name: nom }
            : { output_name: nom, total_units: unites },
      }),

    /** L'état d'un rendu, avancement compté compris. */
    travail: (identifiant) => appeler(`/media/jobs/${identifiant}`),

    /** Annule un rendu. Terminal. */
    annuler: (identifiant, raison = "") =>
      appeler(`/media/jobs/${identifiant}/cancel`, {
        methode: "POST",
        corps: { reason: raison },
      }),
  },
};
