package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"

	"github.com/CesarAchig/api-cli/api"
	"github.com/CesarAchig/api-cli/auth"
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var loginCmd = &cobra.Command{
	Use:   "login",
	Short: "Autenticarse con la API para habilitar operaciones de dataset y entrenamiento",
	Long: `Establece una sesión segura con la plataforma en la nube.
Este comando es un prerrequisito para subir datasets o iniciar
jobs de entrenamiento.

Autenticará las credenciales de usuario y almacenará un token de
sesión local para autorizar futuras peticiones.`,
	RunE: loginCmdRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func loginCmdRun(cmd *cobra.Command, args []string) error {
	username, err := cmd.Flags().GetString("username")
	if err != nil {
		return fmt.Errorf("error obteniendo el flag --username: %w", err)
	}

	sourceURL, err := cmd.Flags().GetString("source")
	if err != nil {
		return fmt.Errorf("error obteniendo el flag --source: %w", err)
	}
	client := api.NewClient(sourceURL)

	ctx := context.Background()
	u, err := url.Parse(config.AppConfig.LoginEndpoint)
	if err != nil {
		return fmt.Errorf("error construyendo la URL de autenticación: %w", err)
	}
	q := u.Query()
	q.Set("userName", username)
	u.RawQuery = q.Encode()

	resp, err := client.Get(ctx, u.String())
	if err != nil {
		return fmt.Errorf("error de autenticación: %w", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(resp, &result); err != nil {
		return fmt.Errorf("error: la respuesta del servidor no es JSON válido")
	}

	token := ""
	if t, ok := result["token"].(string); ok {
		token = t
	}

	if token == "" {
		return fmt.Errorf("error: el servidor no devolvió un token de autenticación")
	}

	creds := auth.Credentials{
		Username:  username,
		Token:     token,
		SourceURL: sourceURL,
	}

	if err := auth.Save(creds); err != nil {
		return fmt.Errorf("error guardando la sesión: %w", err)
	}

	fmt.Printf("¡Inicio de sesión exitoso! Bienvenido, %s.\n", username)
	fmt.Println("Token de sesión almacenado de forma segura.")
	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	loginCmd.Flags().String("username", "", "Nombre de usuario de la plataforma")
	if err := loginCmd.MarkFlagRequired("username"); err != nil {
		panic(err)
	}
	loginCmd.Flags().String("source", "", "URL de la API a la que este cliente enviará las peticiones")
	if err := loginCmd.MarkFlagRequired("source"); err != nil {
		panic(err)
	}
	rootCmd.AddCommand(loginCmd)
}
