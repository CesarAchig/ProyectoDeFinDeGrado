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
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var getStatusCmd = &cobra.Command{
	Use:   "get-status",
	Short: "Recuperar el estado de entrenamiento de un dataset",
	Long: `Consulta a la plataforma en la nube el estado actual de entrenamiento
asociado al dataset especificado.

La respuesta incluye metadatos de la ejecución de MLflow e
información del progreso del trabajo de entrenamiento del modelo.`,
	RunE: getStatusRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func getStatusRun(cmd *cobra.Command, args []string) error {
	datasetName, err := cmd.Flags().GetString("dataset-name")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --dataset-name: %w", err)
	}

	creds, err := requireAuth()
	if err != nil {
		return err
	}

	if creds.SourceURL == "" {
		return fmt.Errorf("Error: no se encontró una URL de API guardada. Ejecuta 'login' primero")
	}
	client := api.NewClient(creds.SourceURL)
	client.AuthToken = creds.Token

	u, err := url.Parse(config.AppConfig.StatusEndpoint)
	if err != nil {
		return fmt.Errorf("Error analizando el endpoint de estado: %w", err)
	}
	q := u.Query()
	q.Set("datasetName", datasetName)
	q.Set("userName", creds.Username)
	u.RawQuery = q.Encode()
	endpoint := u.String()

	ctx := context.Background()
	resp, err := client.Get(ctx, endpoint)
	if err != nil {
		return fmt.Errorf("Error obteniendo el estado: %w", err)
	}

	var prettyJSON map[string]interface{}
	if err := json.Unmarshal(resp, &prettyJSON); err != nil {
		fmt.Println(string(resp))
		return nil
	}

	formatted, err := json.MarshalIndent(prettyJSON, "", "  ")
	if err != nil {
		fmt.Println(string(resp))
		return nil
	}

	fmt.Println(string(formatted))
	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	getStatusCmd.Flags().String("dataset-name", "", "Nombre del dataset para consultar el estado")
	if err := getStatusCmd.MarkFlagRequired("dataset-name"); err != nil {
		panic(err)
	}
	rootCmd.AddCommand(getStatusCmd)
}
