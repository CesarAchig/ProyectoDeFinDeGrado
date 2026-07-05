package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"fmt"

	"github.com/CesarAchig/api-cli/auth"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var logoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Eliminar las credenciales de sesión almacenadas localmente",
	Long: `Elimina el token de autenticación guardado y el nombre de usuario
del almacén local de credenciales.

Necesitarás ejecutar 'login' de nuevo antes de ejecutar
cualquier comando autenticado.`,
	RunE: logoutRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func logoutRun(cmd *cobra.Command, args []string) error {
	if err := auth.Clear(); err != nil {
		return fmt.Errorf("error cerrando la sesión: %w", err)
	}
	fmt.Println("Sesión cerrada correctamente.")
	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	rootCmd.AddCommand(logoutCmd)
}
