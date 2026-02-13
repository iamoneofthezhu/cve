package cveStructs

import (
	"encoding/json"
)

type CVE struct {
	ID           string                 `json:"id" bson:"id"`
	Published    string                 `json:"published" bson:"published"`
	LastModified string                 `json:"lastModified" bson:"lastModified"`
	Status       string                 `json:"vulnStatus" bson:"vulnStatus"`
	Descriptions []Description          `json:"descriptions" bson:"descriptions"`
	Metrics      CVSS                   `json:"metrics" bson:"metrics"`
	Weaknesses   *[]WeaknessDescription `json:"weaknesses,omitempty" bson:"weaknesses,omitempty"`
	References   *[]Reference           `json:"references,omitempty" bson:"references,omitempty"`
}

type Description struct {
	Language string `json:"lang" bson:"lang"`
	Value    string `json:"value" bson:"value"`
}

type CVEOutput struct {
	ID           string      `json:"cve_id" bson:"cve_id"`
	Published    string      `json:"published" bson:"published"`
	LastModified string      `json:"last_modified" bson:"last_modified"`
	Status       string      `json:"status" bson:"status"`
	Descriptions []string    `json:"description" bson:"description"`
	Metrics      CVSS        `json:"metrics" bson:"metrics"`
	Weaknesses   []string    `json:"weaknesses" bson:"weaknesses"`
	References   []Reference `json:"references" bson:"references"`
}

type CVSS struct {
	CvssMetricV30 *[]CVSSMetricV31 `json:"cvssMetricV30,omitempty" bson:"cvssMetricV30,omitempty"`
	CvssMetricV31 *[]CVSSMetricV31 `json:"cvssMetricV31,omitempty" bson:"cvssMetricV31,omitempty"`
	CVSSMetricV40 *[]CVSSMetricV40 `json:"cvssMetricV40,omitempty" bson:"cvssMetricV40,omitempty"`
}

type CVSSMetricV31 struct {
	CVSSData            CVSSData `json:"cvssData" bson:"cvssData"`
	ExploitabilityScore float64  `json:"exploitabilityScore" bson:"exploitabilityScore"`
	ImpactScore         float64  `json:"impactScore" bson:"impactScore"`
}

type CVSSData struct {
	BaseScore    float64 `json:"baseScore" bson:"baseScore"`
	Severity     string  `json:"baseSeverity" bson:"baseSeverity"`
	Vector       string  `json:"vectorString" bson:"vectorString"`
	AttackVector string  `json:"attackVector" bson:"attackVector"`
}

type CVSSMetricV40 struct {
	Source     string   `json:"source" bson:"source"`
	Type       string   `json:"type" bson:"type"`
	CVSS40Data CVSSData `json:"cvssData" bson:"cvssData"`
}

type WeaknessDescription struct {
	Description []Description `json:"description" bson:"description"`
}

type Reference struct {
	URL string `json:"url,omitempty" bson:"url,omitempty"`
}

// Transform converts the raw CVE payload into the normalized document you store in Mongo.
// It also filters to the first English description (if present) and English weaknesses.
// englishWeaknesses and refs are initialized to an empty slice to avoid nil pointer dereference
func Transform(cve CVE) (CVEOutput, error) {
	englishOnly := []string{}
	for _, d := range cve.Descriptions {
		if d.Language == "en" {
			englishOnly = append(englishOnly, d.Value)
			break
		}
	}

	englishWeaknesses := []string{}
	if cve.Weaknesses != nil {
		for _, w := range *cve.Weaknesses {
			for _, d := range w.Description {
				if d.Language == "en" {
					englishWeaknesses = append(englishWeaknesses, d.Value)
					break
				}
			}
		}
	}

	// CVE.References can be nil when input JSON omits "references" (omitempty)
	refs := []Reference{}
	if cve.References != nil {
		refs = *cve.References
	}

	out := CVEOutput{
		ID:           cve.ID,
		Published:    cve.Published,
		LastModified: cve.LastModified,
		Status:       cve.Status,
		Descriptions: englishOnly,
		Metrics:      cve.Metrics,
		Weaknesses:   englishWeaknesses,
		References:   refs,
	}

	// quick sanity check that it can be marshalled (helps catch tag/type issues early)
	if _, err := json.Marshal(out); err != nil {
		return CVEOutput{}, err
	}

	return out, nil
}
