
package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"fmt"
	"regexp"
	"strings"
)

//////////////////////////
//   Config Variables   //
//////////////////////////
// mlflowNameRegex valida nombres compatibles con MLflow Model Registry.
// Debe empezar con alfanumérico y solo contener letras, números, guiones,
// guiones bajos y puntos.
var mlflowNameRegex = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$`)

//////////////////////////
//   Helper Functions   //
//////////////////////////
// validateMLFlowName verifica que un string sea válido para usar en el
// Model Registry de MLflow.
func validateMLFlowName(name string, fieldName string) error {
	if name == "" {
		return fmt.Errorf("el campo '%s' no puede estar vacío", fieldName)
	}
	if !mlflowNameRegex.MatchString(name) {
		return fmt.Errorf(
			"el campo '%s' contiene caracteres no válidos para MLflow Model Registry.\n"+
				"Valor recibido: '%s'\n"+
				"Reglas: solo letras, números, guiones (-), guiones bajos (_) y puntos (.). "+
				"Debe empezar con letra o número. No se permiten espacios, tildes ni caracteres especiales.",
			fieldName, name,
		)
	}
	return nil
}

// sanitizeDatasetName elimina la extensión .csv y valida el nombre base.
func sanitizeDatasetName(fileName string) (string, error) {
	base := strings.TrimSuffix(fileName, ".csv")
	base = strings.TrimSpace(base)
	if err := validateMLFlowName(base, "nombre del dataset"); err != nil {
		return "", err
	}
	return base, nil
}
