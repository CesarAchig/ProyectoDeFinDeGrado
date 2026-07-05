package config

////////////////////
//   Structures   //
////////////////////
type Config struct {
	LoginEndpoint         string
	UploadEndpoint        string
	StartTrainingEndpoint string
	DeleteEndpoint        string
	StatusEndpoint        string
	PredictionEndpoint    string
}

//////////////////////////
//   Config Variables   //
//////////////////////////
var AppConfig = Config{
	LoginEndpoint:         "/auth",
	UploadEndpoint:        "/upload",
	StartTrainingEndpoint: "/training-start",
	DeleteEndpoint:        "/delete-data",
	StatusEndpoint:        "/get-status",
	PredictionEndpoint:    "/get-prediction",
}
