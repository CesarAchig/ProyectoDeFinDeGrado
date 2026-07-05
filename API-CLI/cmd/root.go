package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"fmt"
	"os"

	"github.com/CesarAchig/api-cli/auth"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var rootCmd = &cobra.Command{
	Use:   "api-cli",
	Short: "CLI para subir datasets e iniciar entrenamiento de ML en la nube",
	Long: `Esta herramienta se conecta directamente a la plataforma Cloud ML para
iniciar un flujo de trabajo de machine learning. Gestiona el ciclo de vida de
tus datos procesando peticiones para subir datasets locales a la plataforma.

Además, permite a los usuarios seleccionar datasets específicos de su inventario
e iniciar sesiones de entrenamiento de modelos de forma remota.`,
}

//////////////////////////
//      Functions       //
//////////////////////////
func Execute() {
	err := rootCmd.Execute()
	if err != nil {
		os.Exit(1)
	}
}

func requireAuth() (auth.Credentials, error) {
	creds, err := auth.Load()
	if err != nil {
		return creds, fmt.Errorf("autenticación requerida: %w", err)
	}
	return creds, nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
}
