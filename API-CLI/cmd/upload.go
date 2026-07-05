package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/CesarAchig/api-cli/api"
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var uploadCmd = &cobra.Command{
	Use:   "upload",
	Short: "Subir un dataset a la plataforma",
	Long: `Este comando ejecutará todo el proceso para iniciar el entrenamiento del
modelo de machine learning utilizando el dataset especificado con el flag --dataset.

Debes proporcionar la ruta completa a tu dataset CSV. El comando subirá
el dataset a la plataforma.`,
	RunE: uploadCmdRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func uploadCmdRun(cmd *cobra.Command, args []string) error {
	creds, err := requireAuth()
	if err != nil {
		return err
	}

	datasetPath, err := cmd.Flags().GetString("dataset")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --dataset: %w", err)
	}
	absPath, err := filepath.Abs(datasetPath)
	if err != nil {
		return fmt.Errorf("Error resolviendo la ruta absoluta: %w", err)
	}
	if filepath.Ext(absPath) != ".csv" {
		return fmt.Errorf("el archivo debe tener extensión .csv")
	}
	if _, err := os.Stat(absPath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("archivo de dataset no encontrado en: %s", absPath)
		}
		return fmt.Errorf("error verificando el archivo: %w", err)
	}

	fileName := filepath.Base(datasetPath)

	// --- Validación de nombre compatible con MLflow ---
	if _, err := sanitizeDatasetName(fileName); err != nil {
		return fmt.Errorf("validación de nombre fallida: %w", err)
	}

	data, err := os.ReadFile(absPath)
	if err != nil {
		return fmt.Errorf("Error leyendo el archivo de dataset: %w", err)
	}

	if creds.SourceURL == "" {
		return fmt.Errorf("Error: no se encontró una URL de API guardada. Ejecuta 'login' primero")
	}
	client := api.NewClient(creds.SourceURL)
	client.AuthToken = creds.Token

	ctx := context.Background()
	err = client.Put(ctx, config.AppConfig.UploadEndpoint, fileName, creds.Username, data)
	if err != nil {
		return fmt.Errorf("Error subiendo el dataset: %w", err)
	}

	fmt.Println("¡Subida exitosa!")
	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	uploadCmd.Flags().String("dataset", "", "Ruta donde se encuentra el dataset")
	if err := uploadCmd.MarkFlagRequired("dataset"); err != nil {
		panic(err)
	}
	rootCmd.AddCommand(uploadCmd)
}
