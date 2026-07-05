package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/CesarAchig/api-cli/api"
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var startTrainingCmd = &cobra.Command{
	Use:   "start-training",
	Short: "Iniciar una sesión de entrenamiento de modelo en la nube",
	Long:  `Inicia el proceso de entrenamiento del modelo de Machine Learning usando el dataset especificado.`,
	RunE:  startTrainingRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func startTrainingRun(cmd *cobra.Command, args []string) error {
	datasetName, err := cmd.Flags().GetString("dataset-name")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --dataset-name: %w", err)
	}
	// --- Validación de nombre compatible con MLflow ---
	if _, err := sanitizeDatasetName(datasetName); err != nil {
		return fmt.Errorf("validación de nombre fallida: %w", err)
	}
	targetColumn, err := cmd.Flags().GetString("target-column")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --target-column: %w", err)
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
	// Validar nombre de usuario para MLflow Model Registry
	if err := validateMLFlowName(creds.Username, "nombre de usuario"); err != nil {
		return fmt.Errorf("validación de usuario fallida: %w", err)
	}

	ctx := context.Background()
	resp, err := client.Post(ctx, config.AppConfig.StartTrainingEndpoint, datasetName, creds.Username, targetColumn)
	if err != nil {
		return fmt.Errorf("Error: %w", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(resp, &result); err != nil {
		fmt.Println("Respuesta:", string(resp))
		return nil
	}

	if msg, ok := result["message"].(string); ok {
		fmt.Println(msg)
	}

	if tsResp, ok := result["training_server_response"].(map[string]interface{}); ok {
		if statusCode, ok := tsResp["status_code"].(float64); ok {
			if statusCode >= 500 {
				fmt.Printf("El servidor de entrenamiento respondió con error %d.\n", int(statusCode))
				if body, ok := tsResp["body"].(string); ok {
					fmt.Printf("   Detalle: %s\n", body)
				}
				fmt.Println("   El dataset fue enviado correctamente, pero el entrenamiento no pudo iniciarse.")
			} else if statusCode >= 400 {
				fmt.Printf("  Error %d en el servidor de entrenamiento.\n", int(statusCode))
				if body, ok := tsResp["body"].(string); ok {
					fmt.Printf("   Detalle: %s\n", body)
				}
			} else {
				fmt.Printf("  Servidor de entrenamiento respondió correctamente (%d).\n", int(statusCode))
			}
		}
	}

	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	startTrainingCmd.Flags().String("dataset-name", "", "Nombre del dataset para entrenamiento")
	if err := startTrainingCmd.MarkFlagRequired("dataset-name"); err != nil {
		panic(err)
	}
	startTrainingCmd.Flags().String("target-column", "", "Nombre de la columna objetivo (opcional)")
	rootCmd.AddCommand(startTrainingCmd)
}
